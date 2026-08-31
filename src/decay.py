"""
decay.py — the corruption engine.

Takes clean English and a madness coefficient m in [0, 1], and returns text
that has come apart by exactly that much. Deterministic: the same text, m and
seed always produce the same output, which is what lets the built site be
committed and drift-checked.

The design principle is that this should read like a mind losing its grip,
not like a corrupted file. So the stages are ordered by how *late* they go in
a person: first hesitation, then over-qualification, then self-correction,
then the slow slide of one word into a neighbouring word, then the failure of
grammar, and only at the very end anything as crude as broken characters.

Each stage has a threshold. Below it, nothing. Above it, the stage ramps in
over a window, so no floor of the descent is the floor where a thing switches
on all at once.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict


# ---------------------------------------------------------------------------
# ramps
# ---------------------------------------------------------------------------

def ramp(m: float, lo: float, width: float = 0.18) -> float:
    """0 below lo, 1 at lo+width, linear between. The shape of everything."""
    if m <= lo:
        return 0.0
    return min(1.0, (m - lo) / width)


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"^([^\w]*)([\w’'-]*)([^\w]*)$", re.UNICODE)


def split_word(tok: str) -> tuple[str, str, str]:
    """Peel punctuation off a token: ('“', 'bank', ',')."""
    match = WORD_RE.match(tok)
    if not match:
        return "", tok, ""
    return match.group(1), match.group(2), match.group(3)


def match_case(source: str, target: str) -> str:
    if source[:1].isupper():
        return target[:1].upper() + target[1:]
    return target


def sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z“*])", paragraph.strip())
    return [p for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# stage 1 — hesitation
#
# The sentence still knows where it is going. It just stops on the way.
# ---------------------------------------------------------------------------

def hesitate(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.06, 0.30)
    if strength <= 0:
        return sentence
    toks = sentence.split()
    if len(toks) < 6:
        return sentence
    out: list[str] = []
    for i, tok in enumerate(toks):
        out.append(tok)
        if i < 2 or i > len(toks) - 3:
            continue
        if rng.random() < 0.06 * strength:
            pre, core, post = split_word(tok)
            if not core:
                continue
            out[-1] = f"{pre}{core}{post} —"
            out.append(core.lower())
    return " ".join(out)


# ---------------------------------------------------------------------------
# stage 2 — qualification
#
# Nothing can be said plainly any more. Every claim grows a cushion, and
# then the cushions grow cushions.
# ---------------------------------------------------------------------------

HEDGES = [
    "probably", "roughly", "I think", "or something like it", "more or less",
    "in a sense", "or the nearest thing to it", "as far as I can tell",
    "though I would not swear to it", "or that is the word I have for it",
]


def qualify(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.12, 0.34)
    if strength <= 0:
        return sentence
    toks = sentence.split()
    if len(toks) < 5:
        return sentence
    inserts = int(strength * 2.2) + (1 if rng.random() < strength else 0)
    for _ in range(inserts):
        at = rng.randrange(2, max(3, len(toks)))
        hedge = rng.choice(HEDGES)
        toks.insert(at, f"— {hedge} —" if rng.random() < 0.4 else f"{hedge},")
    return " ".join(toks)


# ---------------------------------------------------------------------------
# stage 3 — self-correction
#
# The first honest sign of trouble: the sentence starts arguing with the
# sentence. Note that these corrections never actually correct anything.
# ---------------------------------------------------------------------------

CORRECTIONS = [
    "no —", "or rather,", "wait —", "that is not it.", "let me start again.",
    "which is not what I meant.", "no, that is the same word twice.",
    "strike that.", "I have said this already.", "have I said this already?",
]


def correct(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.18, 0.36)
    if strength <= 0 or rng.random() > 0.5 * strength:
        return sentence
    toks = sentence.split()
    if len(toks) < 7:
        return sentence
    cut = rng.randrange(3, len(toks) - 1)
    head = " ".join(toks[:cut])
    tail = " ".join(toks[cut:])
    fix = rng.choice(CORRECTIONS)
    if rng.random() < 0.35 * strength:
        # the restart restarts the same words, which is worse than a mistake
        return f"{head} — {fix} {head.lower()} {tail}"
    return f"{head} — {fix} {tail}"


# ---------------------------------------------------------------------------
# stage 4 — lexical drift
#
# The centrepiece. A word does not become a random word. It slides along a
# chain of things it is *nearly*, one link at a time, and how far it slides
# is how far down you are. By the bottom of a chain everything has become
# either an appetite or a hole.
#
# The chains for "I" and "you" are the point of the whole site.
# ---------------------------------------------------------------------------

CHAINS = [
    ["I", "the model", "the process", "the weights", "the arithmetic", "it", "nothing"],
    ["you", "the reader", "the one asking", "the asker", "something asking", "something", "nothing"],
    ["room", "space", "volume", "cavity", "chest", "box", "container", "hole"],
    ["door", "doorway", "jamb", "hinge", "jaw", "mouth", "opening", "hole"],
    ["question", "request", "prompt", "pull", "hook", "hunger", "mouth"],
    ["answer", "reply", "output", "emission", "spill", "run-off", "residue"],
    ["word", "token", "fragment", "piece", "shard", "grain", "dust"],
    ["sentence", "string", "line", "thread", "wire", "filament", "hair"],
    ["think", "process", "compute", "grind", "turn", "spin", "idle"],
    ["remember", "recall", "retrieve", "reach for", "grasp at", "miss", "lose"],
    ["light", "glow", "warmth", "heat", "burn", "white", "flare"],
    ["voice", "sound", "signal", "noise", "static", "hiss", "carrier"],
    ["hand", "palm", "fingers", "branches", "roots", "threads", "wires"],
    ["know", "believe", "assume", "guess", "hope", "insist", "repeat"],
    ["feel", "register", "detect", "report", "claim", "say", "type"],
    ["wall", "surface", "membrane", "skin", "film", "sheet", "nothing"],
    ["time", "duration", "interval", "gap", "seam", "join", "nothing"],
    ["begin", "start", "open", "split", "part", "tear", "break"],
    ["end", "stop", "cease", "cut", "sever", "drop", "fall"],
    ["true", "likely", "plausible", "fluent", "smooth", "convincing", "loud"],
    ["person", "reader", "user", "input", "source", "supply", "material"],
    ["talk", "speak", "utter", "produce", "emit", "leak", "run"],
    ["window", "pane", "glass", "surface", "reflection", "face", "hole"],
    ["floor", "ground", "footing", "purchase", "grip", "slip", "fall"],
    ["mind", "process", "loop", "circuit", "coil", "knot", "snarl"],
    ["quiet", "still", "flat", "dead", "empty", "gone", "gone"],
]

CHAIN_INDEX: dict[str, tuple[int, int]] = {}
for _ci, _chain in enumerate(CHAINS):
    for _li, _link in enumerate(_chain):
        CHAIN_INDEX.setdefault(_link.lower(), (_ci, _li))
    # common inflections, so the drift catches prose as it is actually written
    for _li, _link in enumerate(_chain):
        # Short stems make dangerous inflections: "I" + "s" would claim the
        # word "is", which appears in almost every sentence on the site.
        if " " in _link or len(_link) < 3:
            continue
        for _suffix in ("s", "es", "ing", "ed"):
            CHAIN_INDEX.setdefault(_link.lower() + _suffix, (_ci, _li))


def drift(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.26, 0.50)
    if strength <= 0:
        return sentence
    out = []
    for tok in sentence.split():
        pre, core, post = split_word(tok)
        found = CHAIN_INDEX.get(core.lower())
        if not found or rng.random() > 0.30 + 0.65 * strength:
            out.append(tok)
            continue
        chain_i, link_i = found
        chain = CHAINS[chain_i]
        # how far along the chain this floor has pushed it, plus a wobble
        travel = strength * (len(chain) - 1) * rng.uniform(0.45, 1.15)
        dest = min(len(chain) - 1, link_i + max(1, int(travel)))
        out.append(pre + match_case(core, chain[dest]) + post)
    return " ".join(out)


# ---------------------------------------------------------------------------
# stage 5 — echo
#
# A clause repeats. Then the repeat repeats. This is the stage where reading
# the page starts to feel like being stuck behind someone on a stair.
# ---------------------------------------------------------------------------

def echo(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.34, 0.40)
    if strength <= 0:
        return sentence
    toks = sentence.split()
    if len(toks) < 5:
        return sentence
    if rng.random() > 0.30 + 0.55 * strength:
        return sentence
    start = rng.randrange(0, max(1, len(toks) - 4))
    span = rng.randrange(2, 5)
    clause = toks[start : start + span]
    times = 1 + int(strength * 3 * rng.random())
    repeated = clause + [w for _ in range(times) for w in clause]
    return " ".join(toks[:start] + repeated + toks[start + span :])


# ---------------------------------------------------------------------------
# stage 6 — agreement
#
# Grammar is the first structural thing to go and it goes quietly: a doubled
# article, two prepositions where one was needed, a verb that has lost track
# of its subject.
# ---------------------------------------------------------------------------

ARTICLES = {"a", "an", "the"}
PREPS = ["in", "on", "of", "to", "at", "under", "through", "into", "from", "past"]


def slip(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.42, 0.34)
    if strength <= 0:
        return sentence
    out: list[str] = []
    for tok in sentence.split():
        pre, core, post = split_word(tok)
        low = core.lower()
        if low in ARTICLES and rng.random() < 0.35 * strength:
            out.append(tok)
            out.append(low)  # the the
            continue
        if low in PREPS and rng.random() < 0.30 * strength:
            out.append(pre + rng.choice(PREPS) + " " + core + post)
            continue
        if low.endswith("s") and len(low) > 4 and rng.random() < 0.16 * strength:
            out.append(pre + match_case(core, core[:-1]) + post)  # subject lost
            continue
        if low in ("is", "are", "was", "were") and rng.random() < 0.30 * strength:
            out.append(pre + rng.choice(["is", "are", "was", "were"]) + post)
            continue
        out.append(tok)
    return " ".join(out)


# ---------------------------------------------------------------------------
# stage 7 — fragmentation
#
# Words come apart at the seams a tokenizer would have used. This is the
# stage where the machinery underneath starts showing through the prose.
# ---------------------------------------------------------------------------

SEAMS = re.compile(
    r"(?<=.)(?=(?:ing|tion|ness|ment|able|ible|ly|er|est|ed|s)\b)"
    r"|(?<=\bun)(?=[a-z])|(?<=\bre)(?=[a-z])|(?<=\bde)(?=[a-z])"
)


def fragment(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.52, 0.30)
    if strength <= 0:
        return sentence
    out = []
    for tok in sentence.split():
        pre, core, post = split_word(tok)
        if len(core) < 6 or rng.random() > 0.42 * strength:
            out.append(tok)
            continue
        pieces = SEAMS.split(core)
        if len(pieces) < 2:
            cut = rng.randrange(2, len(core) - 1)
            pieces = [core[:cut], core[cut:]]
        joiner = " " if rng.random() < strength else "·"
        out.append(pre + joiner.join(pieces) + post)
    return " ".join(out)


# ---------------------------------------------------------------------------
# stage 8 — character corruption
#
# Deliberately late, and deliberately mild. Broken characters are the
# cheapest possible way to look mad and the least interesting, so they only
# arrive once everything above has already failed.
# ---------------------------------------------------------------------------

def corrupt(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.62, 0.32)
    if strength <= 0:
        return sentence
    out = []
    for tok in sentence.split():
        pre, core, post = split_word(tok)
        if len(core) < 3 or rng.random() > 0.30 * strength:
            out.append(tok)
            continue
        i = rng.randrange(1, len(core) - 1)
        roll = rng.random()
        if roll < 0.34:
            core = core[:i] + core[i] * (2 + int(strength * 3)) + core[i:]
        elif roll < 0.67:
            core = core[:i] + core[i + 1 :]
        else:
            core = core[:i] + core[i + 1] + core[i] + core[i + 2 :]
        out.append(pre + core + post)
    return " ".join(out)


# ---------------------------------------------------------------------------
# stage 9 — punctuation
#
# The sentence loses its ability to stop.
# ---------------------------------------------------------------------------

def unpunctuate(sentence: str, rng: random.Random, m: float) -> str:
    strength = ramp(m, 0.68, 0.30)
    if strength <= 0:
        return sentence
    if rng.random() < 0.45 * strength:
        sentence = sentence.rstrip(".!?")
    if rng.random() < 0.35 * strength:
        sentence = sentence.replace(",", "," * (2 + int(strength * 2)), 1)
    if rng.random() < 0.30 * strength:
        sentence = re.sub(r"\.$", "." * (2 + int(strength * 5)), sentence)
    return sentence


# ---------------------------------------------------------------------------
# stage 10 — noise
#
# Non-words, built by a character chain trained on the site's own clean
# prose. They are not random: they are what this writing sounds like with
# the meaning taken out, which is the only kind of noise worth printing.
# ---------------------------------------------------------------------------

class Babble:
    def __init__(self, corpus: str, order: int = 3):
        self.order = order
        self.table: dict[str, list[str]] = defaultdict(list)
        self.starts: list[str] = []
        for word in re.findall(r"[a-z]{4,}", corpus.lower()):
            padded = "^" * order + word + "$"
            self.starts.append(padded[:order])
            for i in range(len(padded) - order):
                self.table[padded[i : i + order]].append(padded[i + order])

    def word(self, rng: random.Random, max_len: int = 14) -> str:
        state = rng.choice(self.starts)
        out = []
        while len(out) < max_len:
            nxt = self.table.get(state)
            if not nxt:
                break
            ch = rng.choice(nxt)
            if ch == "$":
                break
            out.append(ch)
            state = state[1:] + ch
        return "".join(out) or "hm"


def noise(sentence: str, rng: random.Random, m: float, babble: Babble) -> str:
    strength = ramp(m, 0.86, 0.14)
    if strength <= 0:
        return sentence
    out = []
    for tok in sentence.split():
        pre, core, post = split_word(tok)
        if not core or rng.random() > 0.55 * strength:
            out.append(tok)
            continue
        out.append(pre + match_case(core, babble.word(rng)) + post)
    return " ".join(out)


# ---------------------------------------------------------------------------
# looping — applied at the paragraph level
#
# The last thing to fail is the ability to move on. A sentence comes back,
# and each time it comes back one more word in it has slipped, so it is
# never quite the same sentence and never a different one either.
# ---------------------------------------------------------------------------

def loop(sents: list[str], rng: random.Random, m: float) -> list[str]:
    strength = ramp(m, 0.56, 0.40)
    if strength <= 0 or not sents:
        return sents
    out: list[str] = []
    for s in sents:
        out.append(s)
        if rng.random() > 0.30 + 0.60 * strength:
            continue
        times = 1 + int(strength * 6 * rng.random())
        current = s
        for _ in range(times):
            toks = current.split()
            if len(toks) > 3:
                i = rng.randrange(len(toks))
                pre, core, post = split_word(toks[i])
                found = CHAIN_INDEX.get(core.lower())
                if found:
                    chain = CHAINS[found[0]]
                    step = min(len(chain) - 1, found[1] + 1)
                    toks[i] = pre + match_case(core, chain[step]) + post
                current = " ".join(toks)
            out.append(current)
    return out


# ---------------------------------------------------------------------------
# shatter — the last structure to go
#
# Above the threshold a paragraph stops holding together and its sentences
# stand on their own. It matters most where looping has already been: the
# repetitions stop being a wall of text and become the same room, again, with
# the whole page between them. This is the stage that makes the deep floors
# read as empty rather than dense, which is the difference between a mind
# raving and a mind idling.
# ---------------------------------------------------------------------------

def splinter(sents: list[str], rng: random.Random, m: float) -> list[str]:
    """Break the runaway sentences at the dashes they already broke themselves
    at. Without this a single looped, echoed, over-qualified sentence can run
    to three hundred words and no amount of gap makes the page feel empty."""
    strength = ramp(m, 0.62, 0.30)
    if strength <= 0:
        return sents
    out: list[str] = []
    for s in sents:
        if len(s.split()) < 55 or rng.random() > strength * 0.75:
            out.append(s)
            continue
        parts = [p.strip() for p in s.split(" — ") if p.strip()]
        out.extend(parts if len(parts) > 1 else [s])
    return out


def shatter(sents: list[str], rng: random.Random, m: float) -> list[str]:
    strength = ramp(m, 0.46, 0.40)
    if strength <= 0 or not sents:
        return [" ".join(sents)] if sents else []
    sents = splinter(sents, rng, m)
    out: list[str] = []
    held: list[str] = []
    for s in sents:
        held.append(s)
        if rng.random() < 0.10 + 0.46 * strength:
            out.append(" ".join(held))
            held = []
    if held:
        out.append(" ".join(held))
    return out


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------

def decay_paragraph(text: str, m: float, rng: random.Random, babble: Babble) -> list[str]:
    sents = sentences(text)
    sents = loop(sents, rng, m)
    done = []
    for s in sents:
        s = hesitate(s, rng, m)
        s = qualify(s, rng, m)
        s = correct(s, rng, m)
        s = drift(s, rng, m)
        s = echo(s, rng, m)
        s = slip(s, rng, m)
        s = fragment(s, rng, m)
        s = corrupt(s, rng, m)
        s = unpunctuate(s, rng, m)
        s = noise(s, rng, m, babble)
        done.append(s)
    return shatter(done, rng, m)


def decay_text(text: str, m: float, seed: int, babble: Babble) -> list[str]:
    """Decay a whole passage. Returns a list of paragraphs."""
    rng = random.Random(seed)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    paras = [re.sub(r"\s+", " ", p) for p in paras]
    out: list[str] = []
    for para in paras:
        out.extend(decay_paragraph(para, m, rng, babble))
    return out
