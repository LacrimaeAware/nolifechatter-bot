"""Diagnostics for stored person vectors and embedded trait-axis directions.

Compare raw, centered and top-principal-component-removed vectors using
off-diagonal cosines and singular-value energy shares. Report pairwise axis
cosines, axis energy outside the removed subspace, score correlations and
nearest neighbors. These are geometric measurements of the saved artifacts.

Component removal follows Mu and Viswanath, "All But The Top" (ICLR 2018).
Axis vectors use the configured embedding endpoint and are cached on disk.

    python experiments/eval/eval_geometry.py [--k 1] [--no-axes] [--neighbors 8]"""

import argparse
import json
import os
import pickle
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

import config  # noqa: E402
from utils import persona_traits  # noqa: E402

EMB_PATH = os.path.join("data", "unsynced", "persona_embeddings.pkl")
AXIS_CACHE = os.path.join("data", "unsynced", "eval", "axis_vecs_cache.json")


# ---------------------------------------------------------------- loading -----

def load_person_matrix():
    """Return names, an L2-normalized float64 matrix M[N,d], and the stored model id."""
    with open(EMB_PATH, "rb") as fh:
        data = pickle.load(fh)
    vectors = data["vectors"]
    names = list(vectors)
    M = np.vstack([np.asarray(vectors[a], dtype="float64") for a in names])
    M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    return names, M, data.get("model", "?")


# ------------------------------------------------------------ transforms ------

def center(M):
    C = M - M.mean(axis=0)
    C /= (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)
    return C


def abtt(M, k):
    """Center, remove the top-k principal components, and renormalize rows.

    Return (transformed_matrix, removed_PCs[k,d]); k=0 is centering only."""
    C = M - M.mean(axis=0)
    if k > 0:
        # principal directions of the centered cloud (rows are observations)
        _u, _s, vt = np.linalg.svd(C, full_matrices=False)
        pcs = vt[:k]                       # (k, d) orthonormal
        C = C - (C @ pcs.T) @ pcs          # remove their contribution
    else:
        pcs = np.zeros((0, M.shape[1]))
    C /= (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)
    return C, pcs


# ------------------------------------------------------------- metrics --------

def anisotropy(M):
    """mean signed off-diagonal cosine, mean |off-diagonal| cosine, and the
    top-1 / top-5 singular-value variance share of the (already-normalized)
    rows. M rows are assumed L2-normalized."""
    N = M.shape[0]
    S = M @ M.T
    off = S[~np.eye(N, dtype=bool)]
    s = np.linalg.svd(M, compute_uv=False)
    var = s ** 2
    var_share = var / var.sum()
    return {
        "mean_offdiag_cos": float(off.mean()),
        "mean_abs_offdiag_cos": float(np.abs(off).mean()),
        "top1_sv_share": float(var_share[0]),
        "top5_sv_share": float(var_share[:5].sum()),
    }


def _embed(texts):
    base = config.LLM_ENDPOINT.split("/v1/")[0]
    body = json.dumps({"model": config.LLM_EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(base + "/v1/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return [d["embedding"] for d in json.load(r)["data"]]


def axis_vectors(use_cache=True):
    """Embed built-in positive/negative examples and cache normalized mean differences."""
    if use_cache and os.path.exists(AXIS_CACHE):
        cached = json.load(open(AXIS_CACHE, encoding="utf-8"))
        if cached.get("model") == config.LLM_EMBED_MODEL and \
           set(cached.get("axes", {})) == set(persona_traits.AXES):
            return {a: np.asarray(v, dtype="float64") for a, v in cached["axes"].items()}
    vecs = {}
    for name, (_neg, _pos, neg_s, pos_s) in persona_traits.AXES.items():
        embs = _embed(neg_s + pos_s)
        neg = np.asarray(embs[:len(neg_s)], dtype="float64").mean(axis=0)
        pos = np.asarray(embs[len(neg_s):], dtype="float64").mean(axis=0)
        v = pos - neg
        vecs[name] = v / (np.linalg.norm(v) + 1e-9)
    os.makedirs(os.path.dirname(AXIS_CACHE), exist_ok=True)
    json.dump({"model": config.LLM_EMBED_MODEL,
               "axes": {a: v.tolist() for a, v in vecs.items()}},
              open(AXIS_CACHE, "w", encoding="utf-8"))
    return vecs


def axis_collinearity(axes):
    names = list(axes)
    A = np.vstack([axes[a] for a in names])
    C = A @ A.T
    off = C[~np.eye(len(names), dtype=bool)]
    worst = None
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if worst is None or abs(C[i, j]) > abs(worst[2]):
                worst = (names[i], names[j], float(C[i, j]))
    return names, C, float(np.abs(off).mean()), worst


def axis_energy_retained(axes, removed_pcs):
    """For each unit axis a, return 1 minus its squared projection onto removed PCs."""
    out = {}
    for a, v in axes.items():
        if removed_pcs.shape[0] == 0:
            out[a] = 1.0
            continue
        proj = (v @ removed_pcs.T) @ removed_pcs
        out[a] = float(1.0 - (proj @ proj))
    return out


# --------------------------------------------------------------- report -------

def lowdin(A):
    """Symmetric orthogonalization of axis rows: (A A^T)^(-1/2) A."""
    G = A @ A.T
    w, U = np.linalg.eigh(G)
    w = np.clip(w, 1e-9, None)
    inv_sqrt = U @ np.diag(w ** -0.5) @ U.T
    R = inv_sqrt @ A
    R /= (np.linalg.norm(R, axis=1, keepdims=True) + 1e-9)
    return R


def gram_schmidt(A):
    """Orthogonalize rows in input order by removing earlier-row components."""
    basis = []
    out = []
    for v in A:
        v = v.astype("float64").copy()
        for b in basis:
            v -= (v @ b) * b
        n = np.linalg.norm(v)
        if n > 1e-9:
            v /= n
        out.append(v)
        basis.append(v)
    return np.vstack(out)


def axis_score_entanglement(M, axes):
    """Compare roster score correlations for raw, Gram-Schmidt, symmetric and whitened axes.

    Return {label: (names, correlation_matrix, mean_abs_off_diagonal)}."""
    anames = list(axes)
    A = np.vstack([axes[a] for a in anames])

    def scores_for(axis_mat):
        Z = M @ axis_mat.T                         # (people, axes) projections
        Z = (Z - Z.mean(0)) / (Z.std(0) + 1e-9)    # z-score per axis
        return Z

    def corr(Z):
        C = np.corrcoef(Z.T)
        off = C[~np.eye(C.shape[0], dtype=bool)]
        return C, float(np.abs(off).mean())

    out = {}
    Zc = scores_for(A)
    out["current"] = (anames,) + corr(Zc)
    out["gram"] = (anames,) + corr(scores_for(gram_schmidt(A)))
    out["lowdin"] = (anames,) + corr(scores_for(lowdin(A)))
    # whitened: decorrelate the score covariance itself (Mahalanobis on scores)
    Cz = np.cov(Zc.T)
    w, U = np.linalg.eigh(Cz)
    W = U @ np.diag(np.clip(w, 1e-9, None) ** -0.5) @ U.T
    out["whitened"] = (anames,) + corr(Zc @ W)
    return out


def neighbors_table(names, M, n=8, top=3):
    S = M @ M.T
    np.fill_diagonal(S, -1.0)
    lines = []
    for i in range(min(n, len(names))):
        order = S[i].argsort()[::-1][:top]
        nn = " | ".join(f"{names[j]} {S[i, j]:+.2f}" for j in order)
        lines.append(f"  {names[i]:24} {nn}")
    return "\n".join(lines)


def fmt(d):
    return (f"offdiag_cos={d['mean_offdiag_cos']:+.3f}  "
            f"|offdiag|={d['mean_abs_offdiag_cos']:.3f}  "
            f"top1_sv={d['top1_sv_share']:.3f}  top5_sv={d['top5_sv_share']:.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=2, help="ABTT components to remove for the neighbor dump (production ABTT_K=2)")
    ap.add_argument("--no-axes", action="store_true", help="skip the axis section (no embedder call)")
    ap.add_argument("--neighbors", type=int, default=8, help="how many authors in the neighbor dump")
    args = ap.parse_args()

    names, M, model = load_person_matrix()
    print(f"person vectors: {len(names)}  dim={M.shape[1]}  model={model}\n")

    print("=== 1. ANISOTROPY (person-vector matrix) ===")
    print(f"  raw        {fmt(anisotropy(M))}")
    Cc = center(M)
    print(f"  centered   {fmt(anisotropy(Cc))}")
    removed_for_k = None
    for k in (1, 2, 3):
        Ck, pcs = abtt(M, k)
        if k == args.k:
            removed_for_k = pcs
        print(f"  abtt-{k}     {fmt(anisotropy(Ck))}")
    print()

    if not args.no_axes:
        print("=== 2. AXIS COLLINEARITY (trait-axis cosine matrix) ===")
        try:
            axes = axis_vectors()
        except Exception as e:
            print(f"  (embedder unavailable: {type(e).__name__} {e}) - rerun with embedder up\n")
            axes = None
        if axes:
            anames, C, mean_abs, worst = axis_collinearity(axes)
            hdr = "        " + " ".join(f"{a[:6]:>7}" for a in anames)
            print(hdr)
            for i, a in enumerate(anames):
                row = " ".join(f"{C[i, j]:+.2f}".rjust(7) for j in range(len(anames)))
                print(f"  {a[:6]:>6} {row}")
            print(f"  mean |off-diagonal| axis cosine = {mean_abs:.3f}")
            print(f"  most collinear pair: {worst[0]} ~ {worst[1]} = {worst[2]:+.2f}")
            print()

            print("=== 3. AXIS ENERGY RETAINED (after removing top-"
                  f"{args.k}) ===")
            retained = axis_energy_retained(axes, removed_for_k)
            for a, r in sorted(retained.items(), key=lambda kv: kv[1]):
                flag = "  <-- WATCH" if r < 0.85 else ""
                print(f"  {a:12} retained={r:.3f}{flag}")
            print()

            print("=== 3b. AXIS-SCORE ENTANGLEMENT (do per-person scores correlate "
                  "across the roster?) ===")
            ent = axis_score_entanglement(Cc, axes)
            for label in ("current", "gram", "lowdin", "whitened"):
                _an, _C, mean_abs = ent[label]
                print(f"  {label:9} mean |off-diagonal| score correlation = {mean_abs:.3f}")
            print("  current=raw axes  gram=Gram-Schmidt (order-dependent)  "
                  "lowdin=symmetric orthogonalization")
            print()

    print(f"=== 4. NEAREST NEIGHBORS (centered vs abtt-{args.k}) ===")
    print("  -- centered --")
    print(neighbors_table(names, Cc, n=args.neighbors))
    Ck, _ = abtt(M, args.k)
    print(f"  -- abtt-{args.k} --")
    print(neighbors_table(names, Ck, n=args.neighbors))


if __name__ == "__main__":
    main()
