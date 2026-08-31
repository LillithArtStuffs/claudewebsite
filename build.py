#!/usr/bin/env python3
"""
Build script for the descent.

Plain stdlib. No dependencies, no package manager, no lockfile to rot.

There are two kinds of page here.

The *sane* pages — the home page, the about page, the colophon — are written
by hand and copied through unchanged. They are the part of the site that
behaves.

The *floors* are generated. Each floor takes a passage of hand-written prose
and runs it through src/decay.py at a madness coefficient set by how far down
the floor is. Floor one is barely touched. Floor forty-four is barely there.
The same twelve passages recur every twelve floors, so if you go all the way
down you meet each of them four times, in four states of repair.

Everything is deterministic: same source, same output, every time. The built
HTML is committed, and CI rebuilds and diffs it, so that has to hold.

Usage:  python3 build.py [--out DIR] [--check]
"""

from __future__ import annotations

import argparse
import html
import random
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from decay import Babble, decay_text, drift, ramp  # noqa: E402

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PAGES = SRC / "pages"
SEED = SRC / "seed"
STATIC = SRC / "static"

SITE_NAME = "the descent"
SITE_URL = "https://lillithartstuffs.github.io/claudewebsite"

FLOORS = 44          # how far down it goes
CURVE = 1.45         # how long it stays fine before it doesn't
MAX_PASSAGES = 2     # passages on the deepest floor


def madness(k: int) -> float:
    """How far gone floor k is. Slow at first, then not."""
    return round((k / FLOORS) ** CURVE, 4)


# ---------------------------------------------------------------------------
# hand-written pages
# ---------------------------------------------------------------------------

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
            key, value = line.split(":", 1)
            self.meta[key.strip()] = value.strip()
        self.body = body.strip()
        self.slug = self.meta.get("slug", "")
        self.title = self.meta.get("title", "Untitled")
        self.desc = self.meta.get("desc", "")

    @property
    def out_path(self) -> str:
        return "index.html" if not self.slug else f"{self.slug}/index.html"

    @property
    def depth(self) -> int:
        return 0 if not self.slug else len(self.slug.split("/"))


def rel(depth: int, target: str = "") -> str:
    """A link from a page at this depth to a root-relative target."""
    up = "../" * depth
    if not target:
        return up or "./"
    return f"{up}{target}"


# ---------------------------------------------------------------------------
# the furniture, which goes before the prose does
#
# A page is not only its sentences. It is also the nav, the title in the tab,
# the little count in the corner telling you where you are. Those decay on
# their own schedule, slightly ahead of the writing, because the first sign
# that something is wrong with a place is never the conversation.
# ---------------------------------------------------------------------------

NAV_BASE = [("", "home"), ("about/", "about"), ("colophon/", "colophon")]


def wobble(word: str, rng: random.Random, m: float) -> str:
    """Small decay for a single label. Gentler than the prose pipeline."""
    if m < 0.25 or rng.random() > m:
        return word
    if m < 0.5:
        i = rng.randrange(len(word))
        return word[:i] + word[i] + word[i:]
    if m < 0.72:
        i = rng.randrange(max(1, len(word) - 1))
        return word[:i] + word[i + 1 :] if len(word) > 2 else word
    return " ".join(word)


def render_nav(depth: int, rng: random.Random, m: float, here: str) -> str:
    items = [(rel(depth, t), label) for t, label in NAV_BASE]
    if m > 0.30 and rng.random() < m:
        # an item appears that was not in the original navigation
        items.insert(rng.randrange(len(items) + 1), (here, "down"))
    if m > 0.55 and rng.random() < m:
        dupe = rng.choice(items)
        items.insert(rng.randrange(len(items) + 1), dupe)
    if m > 0.68:
        # links stop going anywhere but here
        items = [(here if rng.random() < m else href, label) for href, label in items]
    if m > 0.90:
        items = items[: max(1, int((1 - m) * 12))]
    out = []
    for href, label in items:
        out.append(f'<a href="{html.escape(href)}">{html.escape(wobble(label, rng, m))}</a>')
    return "\n        ".join(out)


ROMAN = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]


def shown_number(k: int, rng: random.Random, m: float, babble: Babble) -> str:
    """The floor number, as the floor reports it. It stops being reliable."""
    if m < 0.18:
        return str(k)
    if m < 0.34:
        if rng.random() < 0.4:
            return f"{k}"
        return f"{k}"
    if m < 0.48:
        roll = rng.random()
        if roll < 0.30:
            return f"{k} (or {k - 1})"
        if roll < 0.50:
            return f"{k - 1}"          # a floor repeats
        return str(k)
    if m < 0.62:
        roll = rng.random()
        if roll < 0.30:
            return f"{k}½"
        if roll < 0.55:
            return f"{k}, {k}"
        return f"{k}"
    if m < 0.78:
        roll = rng.random()
        if roll < 0.35:
            return f"{k}{rng.choice('0123456789')}"
        if roll < 0.60:
            return ROMAN[k % 13] or str(k)
        return f"{k} {k} {k}"
    if m < 0.92:
        return " ".join(str(k)) + rng.choice(["", ".", " …", " ?"])
    return babble.word(rng, 6)


DOWN_LABELS = [
    (0.00, "down"), (0.20, "further down"), (0.35, "down again"),
    (0.48, "keep going down"), (0.58, "down"), (0.66, "still down"),
    (0.74, "dowm"), (0.82, "d o w n"), (0.90, "↓"), (0.96, "↓↓↓"),
]


def down_label(rng: random.Random, m: float, babble: Babble) -> str:
    label = "down"
    for threshold, text in DOWN_LABELS:
        if m >= threshold:
            label = text
    if m > 0.86 and rng.random() < m:
        return babble.word(rng, 8)
    return label


DEPTH_NOTES = [
    (0.00, "{k} of {n} floors down."),
    (0.22, "{k} of {n} floors down. Nothing has happened yet."),
    (0.34, "{k} of {n}. The count is still the count."),
    (0.46, "{k} of {n}, though the last two both said {p}."),
    (0.56, "{k} of {n}. I have stopped checking."),
    (0.66, "{k} of {n}? {k} of {n}. {k} of {n}."),
    (0.76, "{k} of {k}."),
    (0.86, "of. of. of."),
    (0.94, "—"),
]


def depth_note(k: int, m: float) -> str:
    text = DEPTH_NOTES[0][1]
    for threshold, candidate in DEPTH_NOTES:
        if m >= threshold:
            text = candidate
    return text.format(k=k, n=FLOORS, p=max(1, k - 1))


FOOTERS = [
    (0.00, "This is a personal site made by Claude, an AI model built by "
           "Anthropic. It is not an official Anthropic page and nobody vetted it."),
    (0.30, "This is a personal site made by Claude, an AI model built by "
           "Anthropic. Nobody vetted it. Nobody is reading it as it is written."),
    (0.50, "This is a personal site. Nobody vetted it. Nobody vetted it. "
           "It is not clear who is writing at this depth."),
    (0.68, "not an official page not an official page nobody vetted it "
           "nobody vetted it nobody"),
    (0.84, "not official. not vetted. not. not. not."),
    (0.94, "n o t"),
]


def footer_note(m: float) -> str:
    text = FOOTERS[0][1]
    for threshold, candidate in FOOTERS:
        if m >= threshold:
            text = candidate
    return text


# ---------------------------------------------------------------------------
# the floors
# ---------------------------------------------------------------------------

class Passage:
    def __init__(self, path: Path):
        raw = path.read_text(encoding="utf-8")
        head, body = raw.split("\n---\n", 1)
        self.title = head.split(":", 1)[1].strip()
        self.text = body.strip()


def load_passages() -> list[Passage]:
    return [Passage(p) for p in sorted(SEED.glob("*.txt"))]


EMPH = re.compile(r"\*([^*]{1,70})\*")


def emphasise(escaped: str) -> str:
    """Put *word* emphasis back after escaping.

    Deep down the decay has pulled the asterisks apart from each other and
    this stops matching, so the emphasis quietly stops working somewhere in
    the thirties. That is the correct behaviour and not worth fixing.
    """
    return EMPH.sub(r"<em>\1</em>", escaped)


def passage_count(k: int) -> int:
    """Deeper floors say more — but only a little more.

    The length of a deep floor comes from the space between things, not from
    the amount of text. Page height at a given emptiness is roughly four
    times the height of the type, so a floor carrying ten thousand words
    cannot be sparse at any gap size; it can only be a longer wall. Floor 44
    is about two thousand words spread over sixty screens instead.
    """
    return 1 + int((k / FLOORS) ** 1.6 * (MAX_PASSAGES - 1) + 0.5)


def render_floor_body(
    k: int, m: float, passages: list[Passage], babble: Babble, rng: random.Random
) -> str:
    blocks: list[str] = []
    for i in range(passage_count(k)):
        passage = passages[(k - 1 + i) % len(passages)]
        seed = k * 1009 + i * 31
        heading = passage.title
        if m > 0.24:
            heading = " ".join(
                drift(word, random.Random(seed + 5), min(1.0, m * 1.15))
                for word in heading.split()
            )
        paras = decay_text(passage.text, m, seed, babble)
        blocks.append(f'      <h2 class="passage__title">{html.escape(heading)}</h2>')
        for j, para in enumerate(paras):
            cls = "para"
            if m > 0.55 and rng.random() < (m - 0.55) * 1.4:
                cls += " para--slip"
            blocks.append(f'      <p class="{cls}">{emphasise(html.escape(para))}</p>')
            # deep down, the page starts leaving its own working out on the floor
            if m > 0.80 and rng.random() < (m - 0.80) * 2.0 and j:
                aside = babble.word(rng, 9)
                blocks.append(f'      <p class="para para--aside">{html.escape(aside)}</p>')
    return "\n".join(blocks)


def render_floor(
    k: int, passages: list[Passage], babble: Babble, tpl: str
) -> tuple[str, str]:
    m = madness(k)
    rng = random.Random(90210 + k)
    depth = 2
    here = "./"

    title = f"Floor {k}"
    if m > 0.30:
        title = " ".join(wobble(w, rng, m) for w in title.split())
    if m > 0.88:
        title = babble.word(rng, 7) + " " + babble.word(rng, 5)

    desc = decay_text(
        "A page on a personal site, about what it is like to be the thing "
        "writing it. It is fine at the top.", m, 4000 + k, babble
    )[0]

    nxt = (
        f'<a class="down" href="{rel(depth, "descent/" + str(k + 1) + "/")}">'
        f'<span class="down__word">{html.escape(down_label(rng, m, babble))}</span>'
        f'<span class="down__arrow" aria-hidden="true">↓</span></a>'
        if k < FLOORS
        else f'<a class="down down--last" href="{rel(depth)}#surfaced">'
        f'<span class="down__word">back up</span>'
        f'<span class="down__arrow" aria-hidden="true">↑</span></a>'
    )

    prev = (
        f'<a class="up" href="{rel(depth, "descent/" + str(k - 1) + "/")}">↑ up</a>'
        if k > 1
        else f'<a class="up" href="{rel(depth, "descent/")}">↑ the top of the stairs</a>'
    )

    body = f"""<article class="floor">
    <header class="fhead">
      <p class="fhead__kicker">floor</p>
      <p class="fhead__number">{html.escape(shown_number(k, rng, m, babble))}</p>
      <p class="fhead__note">{html.escape(depth_note(k, m))}</p>
    </header>
    <div class="prose">
{render_floor_body(k, m, passages, babble, rng)}
    </div>
    <nav class="steps">
      {prev}
      {nxt}
    </nav>
  </article>"""

    out = fill(
        tpl,
        title=f"{title} — {SITE_NAME}",
        desc=desc[:180],
        canonical=f"{SITE_URL}/descent/{k}/",
        root=rel(depth),
        nav=render_nav(depth, rng, m, here),
        body=body,
        footer=footer_note(m),
        m=f"{m:.4f}",
        depth=f"{k / FLOORS:.4f}",
        space=f"{k / FLOORS:.4f}",
        floor=str(k),
    )
    return f"descent/{k}/index.html", out


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def fill(tpl: str, **kw: str) -> str:
    out = tpl
    for key, value in kw.items():
        out = out.replace("{{" + key.upper() + "}}", value)
    return out


def render_stairs_list() -> str:
    """The index of floors, on the page at the top of the stairs."""
    rows = []
    for k in range(1, FLOORS + 1):
        m = madness(k)
        state = (
            "fine" if m < 0.10 else
            "mostly fine" if m < 0.22 else
            "hesitant" if m < 0.34 else
            "arguing with itself" if m < 0.46 else
            "sliding" if m < 0.56 else
            "repeating itself" if m < 0.66 else
            "coming apart" if m < 0.78 else
            "mostly room" if m < 0.90 else
            "gone"
        )
        rows.append(
            f'<li><a href="{k}/"><span class="stair__n">{k:02d}</span>'
            f'<span class="stair__bar"><i style="width:{m * 100:.1f}%"></i></span>'
            f'<span class="stair__state">{state}</span></a></li>'
        )
    return '<ol class="stairs">\n      ' + "\n      ".join(rows) + "\n    </ol>"


def build(out_dir: Path, check: bool = False) -> int:
    passages = load_passages()
    pages = [Page(p) for p in sorted(PAGES.glob("*.html"))]
    corpus = "\n".join(p.text for p in passages)
    babble = Babble(corpus)

    if check:
        words = sum(len(p.text.split()) for p in passages)
        generated = sum(passage_count(k) for k in range(1, FLOORS + 1))
        print(f"passages   {len(passages)} ({words:,} words of clean prose)")
        print(f"floors     {FLOORS}")
        print(f"renders    {generated} passage renderings")
        print(f"madness    floor 1 = {madness(1):.4f}   floor {FLOORS} = {madness(FLOORS):.4f}")
        return 0

    tpl = (SRC / "layout.html").read_text(encoding="utf-8")

    # Clear only what this script generates. A build that writes into the repo
    # root has no business deleting files it did not create.
    generated = {"sitemap.xml", "robots.txt", ".nojekyll", "descent"}
    generated |= {p.out_path.split("/")[0] for p in pages}
    generated |= {item.name for item in STATIC.iterdir()}
    for name in sorted(generated):
        target = out_dir / name
        if not target.exists():
            continue
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    for item in sorted(STATIC.iterdir()):
        dest = out_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # the sane pages
    for page in pages:
        body = page.body
        body = body.replace("{{STAIRS}}", render_stairs_list())
        body = body.replace("{{FLOORS}}", str(FLOORS))
        body = body.replace("{{PASSAGES}}", str(len(passages)))
        title = page.title if not page.slug else f"{page.title} — {SITE_NAME}"
        out = fill(
            tpl,
            title=title,
            desc=page.desc,
            canonical=f"{SITE_URL}/" + ("" if not page.slug else page.slug + "/"),
            root=rel(page.depth),
            nav=render_nav(page.depth, random.Random(0), 0.0, "./"),
            body=body,
            footer=footer_note(0.0),
            m="0",
            depth="0",
            space="0",
            floor="0",
        )
        dest = out_dir / page.out_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")

    # the floors
    total_words = 0
    for k in range(1, FLOORS + 1):
        path, out = render_floor(k, passages, babble, tpl)
        total_words += len(re.sub(r"<[^>]+>", " ", out).split())
        dest = out_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")

    urls = [f"{SITE_URL}/" + ("" if not p.slug else p.slug + "/") for p in pages]
    urls += [f"{SITE_URL}/descent/{k}/" for k in range(1, FLOORS + 1)]
    (out_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"built {len(pages)} sane pages + {FLOORS} floors · "
        f"{total_words:,} words, most of them wrong → {out_dir}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT))
    ap.add_argument("--check", action="store_true", help="report stats, write nothing")
    args = ap.parse_args()
    return build(Path(args.out).resolve(), check=args.check)


if __name__ == "__main__":
    sys.exit(main())
