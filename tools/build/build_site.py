"""Build the standalone project site from its page, docs and synthetic examples."""
from __future__ import annotations

import html
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site"


def relative(target: Path, page: Path) -> str:
    return os.path.relpath(target, page.parent).replace(os.sep, "/")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(value for key, value in attrs if key in {"href", "src"})


def main():
    OUT.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "docs/assets", OUT / "assets", dirs_exist_ok=True)
    css_version = hashlib.sha256((OUT / "assets/pages.css").read_bytes()).hexdigest()[:12]
    index = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    index = index.replace('href="assets/pages.css"', f'href="assets/pages.css?v={css_version}"')
    (OUT / "index.html").write_text(index, encoding="utf-8")
    files = [ROOT / "README.md", ROOT / "PROVENANCE.md", ROOT / "examples/README.md", *sorted((ROOT / "docs").glob("*.md"))]
    for source in files:
        output = OUT / source.relative_to(ROOT).with_suffix(".html")
        output.parent.mkdir(parents=True, exist_ok=True)
        body = markdown.markdown(source.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc"])
        # GitHub accepts escaped table pipes inside inline code; Python-Markdown
        # keeps the backslash. Leave fenced examples untouched.
        body = re.sub(r"(?<!<pre>)<code>(.*?)</code>",
                      lambda match: "<code>" + match[1].replace("\\|", "|") + "</code>",
                      body, flags=re.S)

        def rewrite(match):
            target = html.unescape(match.group(1))
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                return match.group(0)
            actual = (source.parent / unquote(parts.path)).resolve()
            if not actual.is_relative_to(ROOT) or not actual.is_file():
                raise ValueError("Missing or out-of-scope document link: " + source.name)
            if actual.is_relative_to(OUT):
                destination = actual
            else:
                destination = OUT / actual.relative_to(ROOT)
                if actual.suffix == ".md":
                    destination = destination.with_suffix(".html")
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(actual, destination)
            suffix = ("#" + parts.fragment) if parts.fragment else ""
            return 'href="' + html.escape(relative(destination, output) + suffix, quote=True) + '"'

        body = re.sub(r'href="([^"]+)"', rewrite, body)
        title = re.search(r"^# (.+)", source.read_text(encoding="utf-8"), re.M).group(1)
        home = relative(OUT / "index.html", output)
        css = relative(OUT / "assets/pages.css", output) + "?v=" + css_version
        setup = relative(OUT / "docs/SETUP.html", output)
        commands = relative(OUT / "docs/COMMANDS.html", output)
        page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)} · NoLifeChatter</title><link rel="stylesheet" href="{css}"></head><body class="document-page"><a class="skip" href="#content">Skip to content</a><header class="document-header"><a class="brand" href="{home}">NoLifeChatter</a><nav aria-label="Project"><a href="{home}">Overview</a><a href="{setup}">Setup</a><a href="{commands}">Commands</a></nav></header><main class="document-content" id="content">{body}</main><footer class="site-footer"><a href="{home}">NoLifeChatter</a><span>Project documentation</span></footer></body></html>'''
        output.write_text(page, encoding="utf-8")

    messages = []
    for source in sorted((ROOT / "examples/sample-logs/examplechat").glob("*.log")):
        date = re.search(r"\d{4}-\d{2}-\d{2}", source.name).group(0)
        for line in source.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\[(\d\d:\d\d:\d\d)\] (chatter_\d+|examplebot): (.+)", line)
            if match and not re.match(re.escape(match[2]) + r" (?:timed out|untimedout|banned|unbanned) ", match[3]):
                messages.append({"date": date, "time": match[1], "author": match[2], "text": match[3]})
    assert len(messages) == 122, "The sample archive changed; review the presentation count."
    (OUT / "assets/sample-archive.json").write_text(json.dumps(messages, ensure_ascii=False), encoding="utf-8")

    for page in OUT.rglob("*.html"):
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        for target in parser.targets:
            parts = urlsplit(target)
            if not parts.scheme and not parts.netloc and parts.path:
                actual = (page.parent / unquote(parts.path)).resolve()
                if not actual.is_relative_to(OUT) or not actual.exists():
                    raise ValueError("Broken site link in " + str(page.relative_to(OUT)) + ": " + target)
    print(f"Built {len(list(OUT.rglob('*.html')))} pages; links resolve; sample archive has {len(messages)} invented messages.")


if __name__ == "__main__":
    main()
