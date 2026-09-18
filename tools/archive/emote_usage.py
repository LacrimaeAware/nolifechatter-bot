"""Least/most-used 7TV emotes for a channel (offline report).

Shares its counting logic with the live ~leastused command
(utils/emote_usage.py). See that module for the methodology.

Usage:
  python tools/archive/emote_usage.py --seven-tv-set <set_id> --channel <name>
      [--months 6] [--bottom 40] [--top 0] [--names-only]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import emote_usage  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seven-tv-set", required=True)
    ap.add_argument("--channel", required=True)
    ap.add_argument("--months", type=float, default=6)
    ap.add_argument("--bottom", type=int, default=40)
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--min-days", type=float, default=7)
    ap.add_argument("--names-only", action="store_true",
                    help="print just the bottom-N emote names, one per line "
                         "(a removal candidate list - nothing is removed)")
    args = ap.parse_args()

    emotes = emote_usage.seven_tv_set(set_id=args.seven_tv_set)
    if not emotes:
        print("could not fetch the 7TV set", file=sys.stderr)
        sys.exit(1)
    rows = emote_usage.rank(args.channel, emotes, months=args.months,
                            min_days=args.min_days)

    if args.names_only:
        for _rate, _uses, _days, _added, name in rows[:args.bottom]:
            print(name)
        return

    print(f"window: last {args.months:g} months | {len(emotes)} current 7TV "
          f"emotes | {len(rows)} old enough to judge (>= {args.min_days:g}d)")
    print()

    def show(rows_, title):
        print(title)
        print(f"{'emote':32} {'uses':>5} {'per wk':>7} {'available':>10} {'added':>11}")
        for rate, uses, days, added, name in rows_:
            a = time.strftime("%Y-%m-%d", time.localtime(added)) if added else "?"
            print(f"{name:32} {uses:>5} {rate:>7.2f} {days:>8.0f}d {a:>11}")
        print()

    if args.bottom:
        show(rows[:args.bottom], f"LEAST used ({args.bottom}):")
    if args.top:
        show(sorted(rows, key=lambda s: -s[0])[:args.top], f"MOST used ({args.top}):")


if __name__ == "__main__":
    main()
