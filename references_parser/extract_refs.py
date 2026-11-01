#!/usr/bin/env python3
"""Find a paper's reference list in its plain text and clean each entry: title,
year, DOI, authors, and the in-text sentences that cite it.

parse_pdf.parse() strings these helpers together; see README.md.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from titleguess import title_guess, DOI_RE, strip_invisible  # noqa: E402,F401
from parse_refs import (HDR, LIT_HDR, MARK, NAMED_MARK, APA, split_refs,  # noqa: E402,F401
                        split_unlabeled, drop_repeated_lines)

# Material that follows the reference list and is not part of it. Anchored to
# a line start so a mid-sentence "appendix" cannot truncate the list.
APPENDIX_HDR = re.compile(
    r"^[ \t]*(?:APPENDIX|Appendix|APPENDICES|Appendices|"
    r"PH\u1ee4 L\u1ee4C|Ph\u1ee5 l\u1ee5c|"
    r"SUPPLEMENT(?:ARY|S)?|Supplement(?:ary|s)?)\b[^\n]{0,60}$",
    re.M)

# Back matter printed after the list. Left in, it is glued onto the last entry,
# and the citing paper's own DOI from a page header in it was taken as that
# reference's DOI ("ОБ АВТОРАХ" / "AUTHOR INFO", "FINANCING").
# Whole upper-case lines only, so no reference line can match.
BACKMATTER_HDR = re.compile(
    r"^[ \t]*(?:FINANCING|FUNDING|CONFLICTS? OF INTERESTS?|"
    r"AUTHORSHIP CONTRIBUTIONS?|AUTHORS?(?:'|’)? CONTRIBUTIONS?|"
    r"AUTHORS? INFO(?:RMATION)?|ABOUT THE AUTHORS?|"
    r"(?:ИНФОРМАЦИЯ )?ОБ АВТОРАХ|ВІДОМОСТІ ПРО АВТОРІВ)[ \t]*[.:]?[ \t]*$",
    re.M)

YEAR =re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
# Author biographies printed after the list (, : "Biodata" then a
# paragraph per author) were glued onto the last reference.
BIODATA_HDR = re.compile(
    r"^[ \t]*(?:AUTHORS?(?:'|’)?[ \t]+)?(?:BIO-?DATA|Bio-?data|BIOGRAPH(?:Y|IES)|"
    r"Biograph(?:y|ies)|NOTES ON CONTRIBUTORS|Notes on [Cc]ontributors)\b", re.M)
# The article's abstract in its second language, printed after the list
# (an upper-case Vietnamese title, then "Tóm tắt: ...").
SECOND_ABSTRACT = re.compile(r"^[ \t]*(?:Tóm tắt|TÓM TẮT|Abstract|ABSTRACT)[ \t]*[:.]", re.M)


def _is_caps_title(line):
    letters = [c for c in line if c.isalpha()]
    return (not line.strip() or (len(letters) >= 4
            and sum(c.isupper() for c in letters) >= 0.8 * len(letters)))

# A numbered reference line: "[12] A. Author, Title, Journal 1, 2 (2020)."
# The label may stand alone on its line with the entry below it.
NUMBERED_LINE = re.compile(r"^\s*\[\s*(\d{1,3})\s*\.?\s*\](?:\s+\S|\s*$)")


def find_headerless_bibliography(plain):
    """Locate a numbered bibliography that has no 'References' heading.

    APS/Phys. Rev. and many arXiv preprints print the reference list directly
    after the acknowledgments or an appendix, with no heading at all. Those
    papers failed with NO REFERENCE HEADER FOUND even though their list was
    clean and fully numbered [1]..[N].

    Returns the character offset where the list starts, or None. The list is
    only accepted when it is a genuine run of ascending labels starting at 1,
    so a stray "[1]" in the body cannot be mistaken for a bibliography.
    """
    lines = plain.split("\n")
    offsets, cur = [], 0
    for line in lines:
        offsets.append(cur)
        cur += len(line) + 1

    hits = [(i, int(m.group(1)))
            for i, line in enumerate(lines)
            if (m := NUMBERED_LINE.match(line))]
    if len(hits) < 10:
        return None

    # Walk backwards from the end: the bibliography is the LAST ascending run
    # that begins at label 1. Scanning from the end avoids in-text "[1]".
    starts = [k for k, (_, n) in enumerate(hits) if n == 1]
    for k in reversed(starts):
        run, expected = 0, 1
        for _, n in hits[k:]:
            if n == expected:
                run += 1
                expected += 1
            elif n > expected:      # tolerate a label lost to PDF extraction
                expected = n + 1
                run += 1
        if run >= 10:
            return offsets[hits[k][0]]
    return None


# A Vancouver list labelled with a bare number and a space: "8 World Health
# Organization. ... 2022." (J Glob Health). MARK needs "8." or "[8]",
# and "REFERENCES" appeared only as a running page header after the list
# began, so the paper parsed as empty. Too loose to be a general label: it is
# used only by find_bare_numbered_bibliography, and only for a long ascending
# run from 1 whose lines mostly carry a year.
# The separator may carry a stray control character: a paper prints "8 \x07World".
# A dotted "1. González, A., ..." list with no heading at all uses the
# same finder, with the same run and year checks.
BARE_NUMBERED_LINE = re.compile(r"^[ \t]*(\d{1,3})\.?[ \t\x00-\x08\x0b-\x1f]+(?=[A-ZÀ-ỹ])")


def find_bare_numbered_bibliography(plain, min_run=10):
    """Offset of the last ascending "1 Author ..." run, or None."""
    lines = plain.split("\n")
    offsets, cur = [], 0
    for line in lines:
        offsets.append(cur)
        cur += len(line) + 1
    hits = [(i, int(m.group(1))) for i, line in enumerate(lines)
            if (m := BARE_NUMBERED_LINE.match(line))]
    # The year is looked for in the whole entry (up to the next label, at most
    # 8 lines): RSC lists print it after the journal, lines below the label
    # ("1 A. B. Author, ... Statista,\n2024,").
    nxt = {i: (hits[j + 1][0] if j + 1 < len(hits) else len(lines))
           for j, (i, _) in enumerate(hits)}
    for k in reversed([k for k, (_, n) in enumerate(hits) if n == 1]):
        expected, run, dated = 1, 0, 0
        for i, n in hits[k:]:
            if n == expected or expected < n <= expected + 2:
                run += 1
                expected = n + 1
                dated += bool(YEAR.search("\n".join(lines[i:min(nxt[i], i + 8)])))
        if run >= min_run and dated >= run * 0.5:
            return offsets[hits[k][0]]
    return None


def bare_labels_to_dotted(tail):
    """'8 World Health ...' -> '8. World Health ...' so split_refs sees labels."""
    return "\n".join(
        BARE_NUMBERED_LINE.sub(
            lambda m: m.group(1) + ". ",
            line, count=1)
        for line in tail.split("\n"))


def find_headerless_authordate(plain, min_run=10, max_gap=25, max_chars=250_000):
    """(start, end) offsets of the last run of APA entry lines when there is
    no heading, or None.

    One journal prints its APA list straight after
    the author bios, with no "References" line. Accepted only as a dense run
    (at least `min_run` entry starts, each within `max_gap` lines of the
    previous; a page break inside the list adds ~18 lines of furniture) so
    scattered in-text "Smith, J. (2020)" lines cannot qualify. The list ends
    with its last entry, not at the end of the file.
    A document over `max_chars` is a whole volume, not a paper (a paper is
    946k chars of proceedings): it has no single list, so None.
    """
    if len(plain) > max_chars:
        return None
    lines = plain.split("\n")
    offsets, cur = [], 0
    for line in lines:
        offsets.append(cur)
        cur += len(line) + 1
    starts = [i for i, line in enumerate(lines) if APA.match(line.strip())]
    runs, run = [], []
    for i in starts:
        if run and i - run[-1] > max_gap:
            runs.append(run)
            run = []
        run.append(i)
    if run:
        runs.append(run)
    runs = [r for r in runs if len(r) >= min_run]
    if not runs:
        return None
    # The last entry runs on until a blank or numbered line, at most 8 lines.
    last = runs[-1][-1]
    while (last + 1 < len(lines) and last - runs[-1][-1] < 8 and lines[last + 1].strip()
           and not MARK.match(lines[last + 1])):
        last += 1
    return offsets[runs[-1][0]], offsets[last] + len(lines[last])


def merge_stray_labels(refs):
    """Fold a lone out-of-sequence entry into the entry before it.

    A table printed inside the list (Table 7 between [3] and [4])
    contributes a line such as "21. , [26], [29] Note: ..." that reads as
    entry 21. The labels around it run 3, 21, 4: the list resumes exactly
    where it left off, so 21 is not an entry. A wrapped page range reads the
    same way (29, "17. (2012) 4063-4068 ...", 30). A repeated label is left alone: the second 13 is a separate reference
    with a misprinted number.
    """
    labels = [_label_of(r) for r in refs]
    out, i = [], 0
    while i < len(refs):
        if (0 < i < len(refs) - 1 and out
                and None not in (labels[i - 1], labels[i], labels[i + 1])
                and labels[i + 1] == labels[i - 1] + 1
                and labels[i] not in (labels[i - 1], labels[i - 1] + 1)):
            out[-1] = out[-1].rstrip() + " " + refs[i].lstrip()
        else:
            out.append(refs[i])
        i += 1
    return out


def parse_tail(tail):
    """Split a reference-list tail into entries (appendix cut, bug-5 truncation)."""
    # An appendix after the reference list must not be parsed as references.
    # a paper ends with SEL rubric scales numbered 1-4 and 1-8, which
    # split_refs read as numbered entries and produced duplicate labels --
    # tripping the duplicate-label guard and yielding no references at all.
    # A full-width label "1）" (typeset with CJK punctuation) is "1)".
    tail = re.sub(r"(?m)^([ \t]*\d{1,3})）", r"\1)", tail)
    am = APPENDIX_HDR.search(tail)
    if am:
        tail = tail[:am.start()]
    bm = BACKMATTER_HDR.search(tail)
    if bm:
        tail = tail[:bm.start()]
    bd = BIODATA_HDR.search(tail)
    if bd:
        tail = tail[:bd.start()]
    ab = SECOND_ABSTRACT.search(tail)
    if ab:
        # Drop the translated title printed in capitals above the abstract.
        head = tail[:ab.start()].rstrip("\n").split("\n")
        while head and _is_caps_title(head[-1]):
            head.pop()
        tail = "\n".join(head) + "\n"
    refs = split_refs(tail, keep_markers=True)
    refs = merge_stray_labels(refs)
    # Bug 5: a reference list may be followed by an abstract, a second article
    # or a conference programme whose numbering restarts, which used to trip
    # the duplicate-label guard and discard the entire paper. Cut the list at
    # the restart instead -- unless a language-section header explains it.
    if refs:
        _seen = [x for x in (_label_of(r) for r in refs) if x is not None]
        if len(set(_seen)) != len(_seen):
            refs = truncate_at_trailing_matter(refs, tail)
    return refs, tail


def authors_raw(ref, title):
    if title and title in ref:
        head = ref.split(title)[0]
        return re.sub(r"\s+", " ", head).strip(" .,;-–—") or None
    return None


def _first_author_surname(raw):
    """Return the first author surname from the printed reference header."""
    s = re.sub(r"^\s*(?:\[\s*\d+\s*\.?\s*\]|\(\s*\d+\s*\)|\d+[.)])\s*", "", raw)
    m = re.match(r"([A-ZÀ-ỹ][A-Za-zÀ-ỹ'’\-]+)", s)
    return m.group(1) if m else None


# Words that make a first-author chunk an organisation, whose last word alone
# ("Bank", "Education") matches other bodies' citations: a paper "World Bank"
# matched "European Central Bank (2005)".
_ORG_WORDS = re.compile(
    r"\b(?:Bank|Organi[sz]ation|Office|Commission|Nations|Ministry|Department|"
    r"Council|Association|Agency|Institute|Fund|Forum|Union|Group|Programme|"
    r"Program|Committee|Authority|Bureau|Cent(?:re|er)|Government|Corporation|"
    r"Company|Times|Post|News|Newspaper|Statistics?|Province|University|"
    r"Foundation|Society|Board|Services?|Federation|Network|Development)\b"
    r"|\b(?:of|for|and|the|on)\b|&")


def _second_guesses(raw):
    """Surnames to try when _first_author_surname finds no citation.

    The whole first-author chunk as a phrase first -- organisations and
    compound names are cited in full ("World Bank, 2020", "Öztürk Çiftci,
    2021", "Truong Duc Thao") -- then, for a person's name only, its last word,
    for given-name-first lists: "P. W. Rhode and K. S. Strumpf" -> Rhode,
    "Iz Beltagy, Matthew E Peters" -> Beltagy."""
    s = re.sub(r"^\s*(?:\[\s*\d+\s*\.?\s*\]|\(\s*\d+\s*\)|\d+[.)])\s*", "", raw)
    s = re.sub(r"^(?:[A-Z]\.\s*)+", "", s)                 # leading initials
    first = re.split(r",|\s+and\s|\.\s|\s\(|\s\[", s, maxsplit=1)[0].strip(" .")
    words = re.findall(r"[A-Z\u00c0-\u1ef9][A-Za-z\u00c0-\u1ef9'\u2019\-]+", first)
    out = []
    if len(first.split()) >= 2:
        out.append(first)
    if words and not _ORG_WORDS.search(first) and len(first.split()) <= 4:
        out.append(words[-1])
    return out


def _window(body, start, end):
    s = max(0, start - 320)
    e = min(len(body), end + 180)
    return re.sub(r"\s+", " ", body[s:e]).strip()


def contexts_for(body, n, title, raw=None, year=None):
    """Find numerical and author-year citation occurrences in the body.

    Printed bibliography labels are authoritative for numerical styles. For
    author-year styles, match only the first author's surname and the printed
    year; matching every co-author causes common-surname false positives.
    """
    out = []
    for m in re.finditer(r"\[[^\]\n]{0,40}\]", body):
        inner = m.group(0)[1:-1]
        nums = set()
        for part in re.split(r"[,;]", inner):
            part = part.strip()
            if re.fullmatch(r"\d{1,3}", part):
                nums.add(int(part))
            else:
                r = re.fullmatch(r"(\d{1,3})\s*[-–]\s*(\d{1,3})", part)
                if r:
                    nums.update(range(int(r.group(1)), int(r.group(2)) + 1))
        if n in nums:
            frag = _window(body, m.start(), m.end())
            out.append(frag)
        if len(out) >= 6:
            break
    surname = _first_author_surname(raw or "") if raw else None
    years = [int(year)] if year else []
    if raw:
        years.extend(int(y) for y in YEAR.findall(raw) if int(y) not in years)
    found = _author_year_contexts(body, surname, years, out)
    if found is not None:
        return found
    # Nothing found: try the given-name-first reading. Only reached when the
    # first guess matched no citation, so no existing context changes.
    for alt in (_second_guesses(raw) if raw and not out else []):
        if alt != surname:
            found = _author_year_contexts(body, alt, years, out)
            if found is not None:
                return found
            if out:
                break
    return out


def _author_year_contexts(body, surname, years, out):
    """Append author-year citation windows to `out`; return `out` once it is
    full (6), else None after the search."""
    if surname and years:
        for y in years:
            # Covers narrative (Smith et al., 2025), parenthetical
            # (Smith, 2025), and common no-comma variants. The bounded span
            # avoids crossing paragraph boundaries or matching the bibliography.
            name = r"\s+".join(re.escape(w) for w in surname.split())
            pat = (rf"\b{name}\b"
                   rf"(?:\s+et\s+al\.?|\s*(?:&|and)\s+[A-ZÀ-ỹ][\w’'-]+)?"
                   rf"\s*[,;(]?\s*{y}[a-z]?\b")
            for m in re.finditer(pat, body, re.IGNORECASE):
                frag = _window(body, m.start(), m.end())
                if frag not in out:
                    out.append(frag)
                if len(out) >= 6:
                    return out
    return None


# A superscript citation flattened to plain digits by PDF extraction, glued to
# the word it follows: "rich in bioactive substances8. Shijarath".
# Only after a lower-case word of 3+ letters, so "CO2", "nm19" and "pH7" never
# match, and only before punctuation or a space.
_SUPERSCRIPT = re.compile(
    r"(?<=[a-z]{3})(\d{1,3}(?:[,–-]\d{1,3})*)(?=[.,;:]?(?:\s|$))")


# RSC prints the superscript after the punctuation as well as glued to the
# word: "production cost.11", "(NMC).10", "(LCO),3,4". Looser than
# _SUPERSCRIPT ("Fig.3" can match), so superscript_citations tries it only
# when that finds nothing.
_SUPERSCRIPT_AFTER_PUNCT = re.compile(
    r"(?:(?<=[a-z]{3})|(?<=[A-Za-z)][.,)]))"
    r"(\d{1,3}(?:[,–-]\d{1,3})*)(?=[.,;:]?(?:\s|$))")


# A citation set with a full-width bracket after a space: "pharyngitis 7）",
# "Distichochlamys 2）". The bracket is distinctive enough on its own.
_FULLWIDTH_CITATION = re.compile(r"(?<=\s)(\d{1,3}(?:[,–-]\d{1,3})*)）")


def superscript_citations(body, nrefs):
    out = _superscript_citations(body, nrefs, _SUPERSCRIPT)
    return (out
            or _superscript_citations(body, nrefs, _SUPERSCRIPT_AFTER_PUNCT,
                                      skip_names=True)
            or _superscript_citations(body, nrefs, _FULLWIDTH_CITATION))


def _superscript_citations(body, nrefs, pattern, skip_names=False):
    """Citation windows by reference number for a paper cited by superscripts.

    Returns {} unless the paper looks like one: no [n] citations at all, and
    the glued numbers cover at least half the list. That gate keeps "type2
    diabetes" or "sample3" in a bracket- or author-year-cited paper from ever
    becoming a citation.
    """
    if nrefs < 5 or re.search(r"\[\s*\d{1,3}\s*(?:[,;–-]\s*\d{1,3}\s*)*\]", body):
        return {}
    out = {}
    for m in pattern.finditer(body):
        # The looser pattern also meets author affiliation marks glued to a
        # name ("Thi Mai Author1*"): skip a capitalised word.
        if skip_names and re.search(r"(?:^|\s)[A-ZÀ-Ỹ][a-zà-ỹ]+$", body[max(0, m.start() - 40):m.start()]):
            continue
        nums = set()
        for part in m.group(1).split(","):
            r = re.fullmatch(r"(\d{1,3})[–-](\d{1,3})", part)
            if r:
                a, b = int(r.group(1)), int(r.group(2))
                if a < b <= nrefs:
                    nums.update(range(a, b + 1))
            elif part.isdigit():            # "11-2-2" is no label
                nums.add(int(part))
        nums = {x for x in nums if 1 <= x <= nrefs}
        if not nums:
            continue
        frag = _window(body, m.start(), m.end())
        for x in nums:
            ctx = out.setdefault(x, [])
            if len(ctx) < 6 and frag not in ctx:
                ctx.append(frag)
    return out if len(out) >= nrefs / 2 else {}


def _has_numeric_citation(body, n):
    """Whether this particular reference number occurs in a bracket group."""
    for m in re.finditer(r"\[[^\]\n]{0,40}\]", body):
        for part in re.split(r"[,;]", m.group(0)[1:-1]):
            part = part.strip()
            if re.fullmatch(r"\d{1,3}", part) and int(part) == n:
                return True
            r = re.fullmatch(r"(\d{1,3})\s*[-–]\s*(\d{1,3})", part)
            if r and int(r.group(1)) <= n <= int(r.group(2)):
                return True
    return False


# Headings that legitimately restart reference numbering. Multilingual
# Vietnamese journals print "Tiếng Việt" then "Tiếng Anh" and number each
# section from 1, so a repeated label after one of these is real
# and the list must NOT be truncated there.
_LANG_NAMES = (r"Ti\u1ebfng\s+\w+|English|Vietnamese|Korean|Japanese|Chinese"
               r"|French|T\u00e0i\s+li\u1ec7u\s+ti\u1ebfng\s+\w+")
# split_refs absorbs a bare section header into the tail of the PRECEDING
# entry, so it must be looked for there as well as in the gap between entries.
LANG_TRAILING = re.compile(
    r"(?:^|[\s.;:)\]])(?:" + _LANG_NAMES + r")\s*:?\s*$", re.I)
LANG_BETWEEN = re.compile(
    r"^\s*(?:" + _LANG_NAMES + r")\s*:?\s*$", re.M | re.I)


def _label_of(raw):
    """The printed label of a parsed entry, or None."""
    m = re.match(r"^\s*(?:\[\s*(\d{1,3})\s*\.?\s*\]|\(\s*(\d{1,3})\s*\)"
                 r"|(\d{1,3})[.)])\s*", raw)
    if not m:
        return None
    return int(m.group(1) or m.group(2) or m.group(3))


def truncate_at_trailing_matter(refs, tail):
    """Drop entries that follow the end of the bibliography.

    A bibliography's printed labels ascend. When they restart, either a new
    language section began (legitimate -- keep going) or the reference list
    ended and we are now parsing an abstract, a second article or a
    conference programme (truncate there).

    Returns the kept prefix; never fewer than 1 entry.
    """
    labels = [_label_of(r) for r in refs]
    keep = len(refs)
    for i in range(1, len(refs)):
        prev, cur = labels[i - 1], labels[i]
        if prev is None or cur is None or cur > prev:
            continue
        prev_raw = refs[i - 1]
        a = tail.find(prev_raw)
        b = tail.find(refs[i], a + 1 if a >= 0 else 0)
        between = tail[a + len(prev_raw):b] if 0 <= a < b else ""
        if LANG_TRAILING.search(prev_raw.rstrip()) or LANG_BETWEEN.search(between):
            continue    # legitimate language-section restart
        # A lone out-of-order entry is a wrapped fragment mis-read as a new
        # entry -- some papers carry a stray "2. (2008) 325-331." between refs 13
        # and 14 -- not the end of the list. Only treat a restart as real when
        # the sequence does not just resume where it left off.
        if any(x is not None and x > prev for x in labels[i + 1:i + 4]):
            continue
        keep = i
        break
    return refs[:keep] if keep >= 1 else refs
