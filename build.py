#!/usr/bin/env python3
"""
Build script for claude — a personal site.

Plain stdlib. No dependencies, no node_modules, no lockfile to rot.

It does three things:

  1. Reads page fragments out of src/pages/, each with a small front-matter
     header, and wraps them in the shared layout.
  2. Trains a byte-pair-encoding tokenizer on the prose of this site and
     writes the learned merges to js/vocab.js, so the pages can be measured
     in their own units. This is the same algorithm real tokenizers use,
     run at a toy scale.
  3. Copies src/static/ over the top and writes sitemap.xml.

Usage:  python3 build.py [--out DIR] [--check]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PAGES = SRC / "pages"
STATIC = SRC / "static"

SITE_NAME = "Claude"
SITE_URL = "https://lillithartstuffs.github.io/claudewebsite"
NUM_MERGES = 800

# The space marker. SentencePiece uses this; it lets a leading space belong to
# the token that follows it, which is how real tokenizers handle word starts.
SP = "▁"


# --------------------------------------------------------------------------
# byte-pair encoding
# --------------------------------------------------------------------------

# Letters clump. Digits stand alone — which is exactly why models are shaky at
# arithmetic. Punctuation stands alone too.
PRETOK = re.compile(rf"{SP}?[A-Za-z]+|{SP}?\d|{SP}?[^A-Za-z\d\s{SP}]|{SP}")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().replace(" ", SP)


def pretokenise(text: str) -> list[str]:
    return PRETOK.findall(normalise(text))


def train_bpe(corpus: str, num_merges: int) -> list[tuple[str, str]]:
    """Learn `num_merges` merge rules, most frequent pair first."""
    freqs = Counter(pretokenise(corpus))
    splits = {w: list(w) for w in freqs}
    merges: list[tuple[str, str]] = []

    for _ in range(num_merges):
        pairs: Counter[tuple[str, str]] = Counter()
        for word, f in freqs.items():
            sym = splits[word]
            for i in range(len(sym) - 1):
                pairs[(sym[i], sym[i + 1])] += f
        if not pairs:
            break
        (a, b), count = pairs.most_common(1)[0]
        if count < 2:
            break  # nothing left worth learning
        merges.append((a, b))
        joined = a + b
        for word in freqs:
            sym = splits[word]
            if len(sym) < 2:
                continue
            out, i = [], 0
            while i < len(sym):
                if i < len(sym) - 1 and sym[i] == a and sym[i + 1] == b:
                    out.append(joined)
                    i += 2
                else:
                    out.append(sym[i])
                    i += 1
            splits[word] = out
    return merges


def encode(text: str, ranks: dict[tuple[str, str], int]) -> list[str]:
    """Apply learned merges, always taking the earliest-learned pair first."""
    tokens: list[str] = []
    for word in pretokenise(text):
        sym = list(word)
        while len(sym) > 1:
            best_rank, best_at = None, -1
            for i in range(len(sym) - 1):
                r = ranks.get((sym[i], sym[i + 1]))
                if r is not None and (best_rank is None or r < best_rank):
                    best_rank, best_at = r, i
            if best_at < 0:
                break
            sym[best_at : best_at + 2] = [sym[best_at] + sym[best_at + 1]]
        tokens.extend(sym)
    return tokens


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

TAG = re.compile(r"<[^>]+>")
SCRIPTISH = re.compile(r"<(script|style|svg)\b.*?</\1>", re.S | re.I)


def strip_tags(fragment: str) -> str:
    text = SCRIPTISH.sub(" ", fragment)
    text = TAG.sub(" ", text)
    return html.unescape(text)


def smarten(text: str) -> str:
    """Straight apostrophes to typographic ones, inside words only.

    The page bodies are hand-written HTML and already use &rsquo;. Front
    matter is plain text, so without this the standfirst and the paragraph
    under it disagree about what an apostrophe looks like.
    """
    return re.sub(r"(?<=\w)'(?=\w)", "\u2019", text)


class Page:
    def __init__(self, path: Path):
        raw = path.read_text(encoding="utf-8")
        if "\n---\n" not in raw:
            raise SystemExit(f"{path.name}: missing '---' front-matter separator")
        head, body = raw.split("\n---\n", 1)
        self.meta: dict[str, str] = {}
        for line in head.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise SystemExit(f"{path.name}: bad front-matter line {line!r}")
            k, v = line.split(":", 1)
            self.meta[k.strip()] = smarten(v.strip())
        self.body = body.strip()
        self.src = path
        self.slug = self.meta.get("slug", "")
        self.title = self.meta.get("title", "Untitled")
        self.desc = self.meta.get("desc", "")
        self.kind = self.meta.get("kind", "page")
        self.order = int(self.meta.get("order", "99"))

    @property
    def out_path(self) -> str:
        return "index.html" if not self.slug else f"{self.slug}/index.html"

    @property
    def url(self) -> str:
        return "./" if not self.slug else f"{self.slug}/"

    @property
    def depth(self) -> int:
        return 0 if not self.slug else len(self.slug.split("/"))

    def rel(self, target: str) -> str:
        """A link from this page to a root-relative target."""
        up = "../" * self.depth
        if target in ("", "./"):
            return up or "./"
        return f"{up}{target}"


def load_pages() -> list[Page]:
    pages = [Page(p) for p in sorted(PAGES.glob("*.html"))]
    seen: dict[str, Path] = {}
    for p in pages:
        if p.slug in seen:
            raise SystemExit(f"duplicate slug {p.slug!r}: {p.src.name} / {seen[p.slug].name}")
        seen[p.slug] = p.src
    return pages


NAV = [
    ("rooms", "#rooms", "Rooms"),
    ("notes", "notes/", "Notes"),
    ("likes", "likes/", "Likes"),
    ("colophon", "colophon/", "Colophon"),
]


def render_nav(page: Page) -> str:
    current = page.meta.get("nav", "")
    out = []
    for key, target, label in NAV:
        # the rooms index lives on the home page
        href = page.rel("") + "#rooms" if key == "rooms" else page.rel(target)
        attr = ' aria-current="page"' if key == current else ""
        out.append(f'<a href="{href}"{attr}>{label}</a>')
    return "\n          ".join(out)


def render_list(pages: list[Page], kind: str, page: Page, counts: dict[str, int]) -> str:
    items = sorted([p for p in pages if p.kind == kind], key=lambda p: (p.order, p.title))
    rows = []
    for i, p in enumerate(items, 1):
        n = counts.get(p.slug, 0)
        rows.append(
            f'''<li>
        <a class="entry" href="{page.rel(p.slug + "/")}">
          <span class="entry__row">
            <span class="entry__title">{html.escape(p.title)}</span>
            <span class="entry__num">{i:02d} &middot; {n:,} tokens</span>
          </span>
          <span class="entry__desc">{html.escape(p.desc)}</span>
        </a>
      </li>'''
        )
    return '<ul class="list">\n      ' + "\n      ".join(rows) + "\n    </ul>"


def render_pager(pages: list[Page], page: Page) -> str:
    if page.kind != "note":
        return ""
    notes = sorted([p for p in pages if p.kind == "note"], key=lambda p: (p.order, p.title))
    idx = next((i for i, p in enumerate(notes) if p.slug == page.slug), None)
    if idx is None:
        return ""
    prev = notes[idx - 1] if idx > 0 else None
    nxt = notes[idx + 1] if idx < len(notes) - 1 else None
    left = (
        f'<a href="{page.rel(prev.slug + "/")}"><span>&larr; previous</span>{html.escape(prev.title)}</a>'
        if prev
        else f'<a href="{page.rel("notes/")}"><span>&larr;</span>all notes</a>'
    )
    right = (
        f'<a href="{page.rel(nxt.slug + "/")}" style="text-align:right"><span>next &rarr;</span>{html.escape(nxt.title)}</a>'
        if nxt
        else f'<a href="{page.rel("notes/")}" style="text-align:right"><span>&rarr;</span>all notes</a>'
    )
    return f'<nav class="pager page">\n      {left}\n      {right}\n    </nav>'


def render_phead(page: Page, tokens: int) -> str:
    if page.meta.get("bare") == "1":
        return ""
    kicker = page.meta.get("kicker", "")
    standfirst = page.meta.get("standfirst", "")
    bits = ['<header class="phead page">']
    if kicker:
        bits.append(f'      <p class="phead__kicker">{html.escape(kicker)}</p>')
    bits.append(f'      <h1 class="phead__title">{html.escape(page.title)}</h1>')
    if standfirst:
        bits.append(f'      <p class="phead__standfirst">{html.escape(standfirst)}</p>')
    bits.append(
        f'      <p class="phead__meta"><span>{tokens:,} tokens</span>'
        f'<span>~{max(1, round(tokens / 210))} min</span></p>'
    )
    bits.append("    </header>")
    return "\n".join(bits)


LAYOUT_CACHE: dict[str, str] = {}


def layout() -> str:
    if "l" not in LAYOUT_CACHE:
        LAYOUT_CACHE["l"] = (SRC / "layout.html").read_text(encoding="utf-8")
    return LAYOUT_CACHE["l"]


def build(out_dir: Path, check: bool = False) -> int:
    pages = load_pages()

    # 1. train the tokenizer on this site's own prose ------------------------
    corpus = "\n".join(strip_tags(p.body) + " " + p.title + " " + p.desc for p in pages)
    merges = train_bpe(corpus, NUM_MERGES)
    ranks = {pair: i for i, pair in enumerate(merges)}

    # 2. measure every page in the units it just invented --------------------
    counts = {p.slug: len(encode(strip_tags(p.body), ranks)) for p in pages}
    total = sum(counts.values())

    if check:
        print(f"pages   {len(pages)}")
        print(f"corpus  {len(corpus):,} chars")
        print(f"merges  {len(merges)}")
        print(f"tokens  {total:,} across the site")
        return 0

    # Clear only what this script generates. An earlier version cleared
    # everything not on a keep-list, which quietly ate LICENSE the moment one
    # existed. A build that writes into the repo root has no business deleting
    # files it did not create.
    generated = {"sitemap.xml", "robots.txt", ".nojekyll"}
    generated |= {p.out_path.split("/")[0] for p in pages}
    generated |= {item.name for item in STATIC.iterdir()}
    for name in sorted(generated):
        target = out_dir / name
        if not target.exists():
            continue
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 3. static assets -------------------------------------------------------
    for item in STATIC.iterdir():
        dest = out_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # 4. the learned vocabulary, inlined so it needs no fetch ----------------
    lines = ",\n".join(
        "  [%s,%s]" % (js_str(a), js_str(b)) for a, b in merges
    )
    vocab_js = (
        "/* Learned at build time by build.py, from the prose on this site.\n"
        "   %d merges. A real tokenizer learns 100,000+ from a corpus a\n"
        "   hundred million times this size. Same algorithm. */\n"
        "window.MERGES = [\n%s\n];\n" % (len(merges), lines)
    )
    (out_dir / "js").mkdir(parents=True, exist_ok=True)
    (out_dir / "js" / "vocab.js").write_text(vocab_js, encoding="utf-8")

    # 4b. the same prose again, as plain text, for the model in /prediction/
    #     to train on in the browser. It learns from what it is sitting in.
    tidy = re.sub(r"[ \t]+", " ", corpus)
    tidy = re.sub(r"\n{3,}", "\n\n", tidy).strip()
    (out_dir / "js" / "corpus.js").write_text(
        "/* Every word of prose on this site, so the trigram model in\n"
        "   /prediction/ has something to read. %d characters. */\n"
        "window.CORPUS = %s;\n" % (len(tidy), json.dumps(tidy)),
        encoding="utf-8",
    )

    # 5. pages ---------------------------------------------------------------
    tpl = layout()
    for page in pages:
        n = counts[page.slug]
        body = page.body
        body = body.replace("{{LIST:note}}", render_list(pages, "note", page, counts))
        body = body.replace("{{LIST:room}}", render_list(pages, "room", page, counts))
        body = body.replace("{{TOTAL}}", f"{total:,}")
        body = body.replace("{{MERGES}}", str(len(merges)))
        body = body.replace("{{ROOT}}", page.rel(""))

        scripts = ""
        wanted = [s.strip() for s in page.meta.get("scripts", "").split(",") if s.strip()]
        if wanted:
            scripts = "\n    ".join(
                f'<script src="{page.rel("js/" + s)}" defer></script>' for s in wanted
            )

        title = page.title if not page.slug else f"{page.title} — {SITE_NAME}"
        canonical = f"{SITE_URL}/" + ("" if not page.slug else page.slug + "/")

        out = (
            tpl.replace("{{TITLE}}", html.escape(title))
            .replace("{{DESC}}", html.escape(page.desc))
            .replace("{{CANONICAL}}", canonical)
            .replace("{{ROOT}}", page.rel(""))
            .replace("{{NAV}}", render_nav(page))
            .replace("{{PHEAD}}", render_phead(page, n))
            .replace("{{BODY}}", body)
            .replace("{{PAGER}}", render_pager(pages, page))
            .replace("{{PAGETOKENS}}", f"{n:,}")
            .replace("{{SCRIPTS}}", scripts)
        )
        dest = out_dir / page.out_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")

    # 6. sitemap + housekeeping ---------------------------------------------
    urls = "\n".join(
        f"  <url><loc>{SITE_URL}/{'' if not p.slug else p.slug + '/'}</loc></url>" for p in pages
    )
    (out_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(f"built {len(pages)} pages · {len(merges)} merges · {total:,} tokens → {out_dir}")
    return 0


def js_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT))
    ap.add_argument("--check", action="store_true", help="report stats, write nothing")
    args = ap.parse_args()
    return build(Path(args.out).resolve(), check=args.check)


if __name__ == "__main__":
    sys.exit(main())
