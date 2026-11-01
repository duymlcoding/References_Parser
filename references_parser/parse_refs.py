import re

# A reference-section heading. A leading section number ("5. REFERENCES",
# "8 References") and a short trailing qualifier ("Reference List",
# "REFERENCES AND NOTES") are both common and were previously missed, because
# the heading word had to be alone on the line. The match stays anchored to a
# whole line and the suffix is capped at a few words, so prose mentioning
# "references" cannot match.
#
#  (all whole-line, so prose still cannot match):
#   "VI. REFERENCES"            a Roman-numeral section number
#   "REFERENCES AND BIBLIOGRAPHY"
#   "Works Citation"
#   "Библиографический список / References"  a Cyrillic heading before the
#                               English one, as RUDN journals print it
#   "Referencesa"               one stray glyph glued on by the text layer
#                               (Cogent); only after the full word
#
#  (still whole-line):
#   "References."               a trailing period
#   "G. REFERENCES"             a lettered section
#   "░ REFERENCES"              a decorative glyph before the word
#   "СПИСОК ЛИТЕРАТУРЫ | REFERENCES"  "|" instead of "/"
#   "BIBLIOGRAPHIC REFERENCES"
#   "R e f e r e n c e s"       letter-spaced typesetting
#   "TÀI LIỆU THAM KHẢO (REFERENCES)"  a bracketed English gloss
#   "Tài liӋu tham khҧo"        a legacy Vietnamese font read as Cyrillic
HDR = re.compile(
    r"^[ \t]*(?:[░■□▪●◆♦►•][ \t]*)?"
    r"(?:\d{1,2}[.)]?[ \t]+|[IVXL]{1,5}\.[ \t]+|[A-H]\.[ \t]+)?"
    r"(?:[Ѐ-ӿ][Ѐ-ӿ \t ]{2,60}[/|][ \t ]*)?"
    r"(?:BIBLIOGRAPHIC[ \t]+|Bibliographic[ \t]+)?"
    r"(?:REFERENCES[a-z]?|REFERENCE|References[a-z]?|Reference|TÀI LIỆU THAM KHẢO|"
    r"Tài liệu tham khảo|TAI LIEU THAM KHAO|Tài liӋu tham khҧo|BIBLIOGRAPHY|Bibliography|"
    r"WORKS CITED|Works Cited|WORKS CITATION|Works Citation|"
    r"LITERATURE CITED|Literature Cited|"
    r"R[ \t]e[ \t]f[ \t]e[ \t]r[ \t]e[ \t]n[ \t]c[ \t]e[ \t]s|"
    r"R[ \t]E[ \t]F[ \t]E[ \t]R[ \t]E[ \t]N[ \t]C[ \t]E[ \t]S)"
    r"(?:[ \t]+(?:AND[ \t]+NOTES|and[ \t]+notes|AND[ \t]+BIBLIOGRAPHY|"
    r"and[ \t]+Bibliography|List|LIST|Cited|CITED|"
    r"\((?:REFERENCES|References)\)))?"
    r"[ \t]*[.:]?[ \t]*$",
    re.M)

# A bare "Literature" heading (Polish/Central-European journals print
# "Literature" or "Literatura" for the reference list). Too generic to
# trust alongside HDR, so extract_refs consults it only when HDR finds nothing.
LIT_HDR = re.compile(r"^[ \t]*(?:LITERATURE|Literature|LITERATURA|Literatura)[ \t]*:?[ \t]*$",
                     re.M)

# A named label used by CS/AI bibliographies: [Akrami et al., 2022].
# These carry no number, so the printed label cannot be an int; extract_refs
# falls back to positional numbering for them.
# "[Accessed: 20 March 2025]" and "[Online: 5 May 2024]" have the same shape
# as a named label and were matching it, which on a paper glued 23 author-date
# references into 3 blobs. Apparatus words are excluded, and a "Word: date"
# construction is rejected outright -- a real named label is author-like.
_NAMED_STOP = (r"Accessed|Online|Available|Retrieved|Viewed|Cited|Downloaded"
               r"|Internet|Last|Updated|Accessed\s+on|In\s+press")
NAMED_MARK = re.compile(
    r"^\s*\[(?!(?:" + _NAMED_STOP + r")\b)"
    r"([A-Z\u00c0-\u1ef9][^\]\n:]{2,60}?,?\s*\d{4}[a-z]?)\]\s*(.*)$")

# a marker that begins a reference: [1] / (1) / 1. / 1) - possibly alone on its line
# MARK_TIGHT also accepts "1.WHO." -- a Vancouver list typeset with no
# space after the label. The bare-number case still requires a
# following space or end-of-line so a decimal like "3.5" is not a label.
# "[16.]" (a period inside the brackets) is the same label as
# "[16]"; it was not recognised, so both bibliographies parsed as empty.
MARK = re.compile(r"^\s*(?:\[\s*(\d{1,3})\s*\.?\s*\]|\(\s*(\d{1,3})\s*\)|(\d{1,3})[.)](?:\s+|$|(?=[A-Z\u00c0-\u1ef9])))\s*(.*)$")
MARK_TIGHT = True
# APA author-date:  Nguyen, T. V. (2023). or Agarwal S (2020)
APA = re.compile(r"^[A-ZÀ-ỹ][\w’'\-]*[,\s][^()]{0,120}?\(\d{4}[a-z]?\)")

# Author-date starts APA above misses :
#   "Al Badi, I. A. H. (2015, January)."  a dated item: month, maybe a day
#   "Cremin, T., ... Swann, J. (Eds.). (2017)."  an editor/role parenthesis
#   "Tinti-Kane, H. (Director). (2014)."
#   "van den Boom-Muilenburg, S. N., ..."  a lower-case surname particle
#   "CAS-well. (2025). 2024 ESG Report"  a corporate author ending in "."
#   "Grammarly. (n.d.). About us."  an undated web page
_PARTICLES = r"(?:(?:van|von|de|der|den|da|du|di|le|la|del|dos)\s+)*"
_APA_YEAR = (r"(?:\((?:Eds?|Ed|Director|Producer|Trans|Comp|Host)\.?\)\.?\s*)?"
             r"\((?:\d{4}[a-z]?(?:,\s*[A-Z][a-z]+\.?(?:\s+\d{1,2})?)?|n\.\s?d\.)\)")
APA_X = re.compile(r"^" + _PARTICLES + r"[A-ZÀ-ỹ][\w’'\-]*"
                   r"(?:[,\s][^()]{0,120}?|\.\s*)" + _APA_YEAR)
# A long author list wraps before its year (ten authors, or
# "(2023)." alone on the next line). The line must open like
# an author ("Surname, I."), and the year is looked for in the next two lines.
# A surname alone on its line ("Smith," / "S." / "(2022, July 24).") is how
# the text layer breaks some entries.
AUTHOR_START = re.compile(r"^" + _PARTICLES + r"[A-ZÀ-ỹ][\w’'\-]+,\s*"
                          r"(?:(?:[A-ZÀ-ỹ]\.\s*-?\s*){1,4}(?:[,&]|$)|$)")
APA_LONG = re.compile(r"^" + _PARTICLES + r"[A-ZÀ-ỹ][\w’'\-]*,[^()]{0,450}?"
                      + _APA_YEAR)
# Elsevier/Harvard: Aguilera, D.A., Perez, A., 2011.
HARV = re.compile(r"^[A-ZÀ-ỹ][\w’'\-]*,\s*(?:[A-ZÀ-ỹ]\.){1,3}.{0,140}?,\s*\d{4}[a-z]?\.")
# Chicago / author-date with a spelled-out author list and a bare year:
#   Aerts, Raf, Olivier Honnay, and An Van Nieuwenhuyse. 2018. "Biodiversity..."
#   Wang, PoChing, and Chi-Ying Yu. 2018. "Aesthetic experience as..."
# APA requires "(2018)" and HARV requires initials ("Aerts, R., 2018."), so
# neither matched and these bibliographies had no recognised start line.
# The author run may contain periods, because initials do: a paper
# "Adams, K., S. Hean, P. Sturgis, and J. M. Clark. 2006." was missed by the
# original [^.] run, which stopped at the first initial. A period is allowed
# only when a single capital precedes it (an initial), never a sentence end,
# and the entry must continue like a title -- an opening quote, capital or
# digit -- so a wrapped prose line is not read as a new reference.
CHICAGO = re.compile(
    r"^[A-Z\u00c0-\u1ef9][\w\u2019'\-]*,\s+"
    r"(?:[^.\d]|(?<=\b[A-Z])\.)"
    r"{1,200}?"
    r"\.\s*\d{4}[a-z]?\.\s+"
    r"[\u201c\u2018\"'A-Z\u00c0-\u1ef9\d]")

# AAS / astronomy: author list, then a COMMA before the year.
#   Zevin, M., Bavera, S. S., Berry, C. P. L., et al. 2021, ApJ, 910, 152
#   Wette, K., & Prix, R. 2013, Phys. Rev. D, 88, 123005
# A continuation line such as "99, 084026" or "PhRvD, 104, 063030" must not
# match, so a surname followed by an initial is required before the year.
AAS = re.compile(
    r"""^[A-Z\u00c0-\u1ef9][\w\u2019'\-]+,\s*[A-Z]\.   # Surname, J.
        [^\d]{0,200}?                                   # rest of the authors
        \s\d{4}[a-z]?\s*,\s                             # 2015,
     """, re.X)

# AAAI / IJCAI: authors separated by semicolons, year with a period.
#   Chen, R. T. Q.; Rubanova, Y.; and Duvenaud, D. K. 2018. Neural ODEs.
SEMI = re.compile(
    r"^[A-Z\u00c0-\u1ef9][\w\u2019'\-]+,\s*(?:[A-Z]\.\s*){1,4};"
    r".{0,200}?\.\s*\d{4}[a-z]?\.\s")

# running headers / page furniture
NOISE = re.compile(
    r"^(\d+\s+of\s+\d+|Page \d+|https?://\S+$|[A-Z][a-z]+ \d{4},\s*\d+,\s*\d+"
    # A journal running header repeated on every page. It carries a year in
    # parentheses, so APA matched it and it became a phantom reference --
    # a paper produced two ("JOURNAL OF X STUDIES, VOL. 40, NO. 1
    # (2024) 182"). Recognised by being mostly upper case with VOL/NO and no
    # author-initial pattern.
    r"|[A-Z][A-Z\s,.:;()\-\u2013\u2014&\u0110\u00c0-\u1ef9]{12,}"
    r"(?:VOL|NO)\.?\s*\d+[^a-z]*"
    # A running header carrying the journal's ISSN: "Tạp chí X (2025),
    # 25(8), 12-17 ISSN: 2354-0753" matched APA as a reference.
    r"|.{0,80}\bISSN:?\s*\d{4}-?\d{3}[\dXx]\b.{0,40}"
    # An author running header: "Author, A. B., Author, C. D., ... Vol. 2;
    # No. 1; 2025", read as a long author list once AUTHOR_START
    # began looking ahead for the year.
    r"|.{0,200}\bVol\.?\s*\d+;\s*No\.?\s*\d+;\s*\d{4}"
    r")$")


# A labelled line that continues the previous reference, where the furniture
# is separated from the phantom label by a space:
#   "11. (2008) 1497-1505. doi:10.1016/j.carbon.2008.06.048."
#   "5. 2985 (2020). DOI: https://doi.org/10.1021/acs.est.9b04975"
#   "95. [136] Q. Gao, ..."  -- a second printed label on the same line
CONTINUATION_SPACED = re.compile(
    r"""^\s*\d{1,3}[.)]\s+(?:
          \(\s*\d{4}\s*\)\s*\d          # "(2008) 1497"
        | \d{3,6}\s*\(\s*\d{4}\s*\)     # "2985 (2020)"
        | \[\s*\d{1,3}\s*\]              # "[136] Q. Gao"
        | (?:doi|DOI|URL|PMID|PMCID)\b
      )""",
    re.X)

# A table row whose first column is a citation number. A reference is prose;
# a table row is mostly numeric tokens.
NUMERIC_ROW = re.compile(r"^\s*\d{1,3}[.)]\s+(?=.*\d)(?P<rest>.+)$")


def _is_numeric_row(line):
    return _is_numeric_row_text(line)


# Furniture that can follow a bare number without the number being a label.
_FURNITURE_NEXT = re.compile(
    r"""^\s*(?:
          \(\s*\d{4}\s*\)                 # "(2020)."
        | \d{2,6}\s*\(\s*\d{4}\s*\)        # "2985 (2020)." - page then year
        | \d{1,5}\s*[-\u2013\u2014]\s*\d    # "1497-1505."
        | [:;,]                            # ":54-9."
        | (?:doi|DOI|URL|PMID|PMCID|https?://)
      )""",
    re.X)


def _merge_would_be_furniture(num, nxt):
    """True when gluing `num` onto `nxt` would invent a label rather than
    restore one."""
    if _FURNITURE_NEXT.match(nxt):
        return True
    joined = f"{num}. {nxt}"
    return _is_numeric_row_text(joined)


def _is_numeric_row_text(line):
    m = NUMERIC_ROW.match(line)
    if not m:
        return False
    toks = m.group("rest").split()
    if len(toks) < 3:
        return False
    numeric = sum(1 for t in toks
                  if re.fullmatch(r"[\d.,;:%\u00d7x/+-]+|N/A", t, re.I))
    return numeric >= max(2, len(toks) * 0.5)


def merge_lone_markers(lines):
    """A number alone on its line belongs to the text that follows it --
    unless that text is page/volume furniture or a table row, in which case
    the number was never a label."""
    out, i = [], 0
    while i < len(lines):
        m = MARK.match(lines[i])
        if m and not (m.group(4) or "").strip() and i + 1 < len(lines):
            n = m.group(1) or m.group(2) or m.group(3)
            nxt = lines[i + 1].strip()
            if _merge_would_be_furniture(n, nxt):
                out.append(lines[i])
                i += 1
                continue
            out.append(f"{n}. {nxt}")
            i += 2
        else:
            out.append(lines[i])
            i += 1
    return out


# A wrapped line whose leading number is NOT a reference label. A reference
# broken across a page or column resumes with its own volume/page furniture,
# and MARK read those leading digits as a new label:
#   "...Eur J Oncol Nurs. 2015 Feb; 19" + "(1):54-9. https://doi.org/..."
#       -> phantom label (1)
#   "...Lancet. 2010; 376: 1517-21." + "29. De Souza GE, ..."
#       -> phantom label 29 inside entry 9
# Each produced a duplicate printed label, tripping the duplicate-label guard
# in extract_refs, so one wrapped reference cost the whole paper. A real entry
# starts with an author or a title, never with a page range, a bare DOI/PMID,
# or a second label.
# A wrapped line that opens with bare issue/page furniture and no label at
# all: "...Eur J Oncol Nurs. 2015 Feb; 19" wraps to "(1):54-9. https://...".
# MARK's "(N)" branch read the issue number as a printed label.
LEADING_ISSUE = re.compile(
    r"""^\s*(?:
          \(\s*\d{1,4}\s*\)\s*[:;,]      # "(1):54-9."
        | [:;]\s*\d                       # ":54-9."
      )""",
    re.X)

# A numbered line whose text resumes in lower case is a continuation, not a
# new entry: a paper wrapped "...Search Methods for ... Signals" onto
# "1. the signal and its detection, Phys. Rev. D 58, 063001 (1998)."
# Function words that cannot begin a surname or a title-initial author name.
# Deliberately excludes name particles (van, von, de, du, da, dos, del, le,
# la, ter, ten, bin) -- a paper "4. van der Laak J, ..." is a real entry, and
# an earlier broad [a-z]+ pattern swallowed it into the previous reference.
RESUME_WORDS = (
    r"the|and|or|of|in|on|for|with|to|from|its|their|his|her|by|at|as|"
    r"is|are|was|were|that|which|this|these|those|but|nor|into|onto|"
    r"through|during|between|among|within|without|under|over|about"
)

# A numbered line whose text resumes with a function word is a continuation,
# not a new entry: a paper wrapped "...Search Methods for ... Signals" onto
# "1. the signal and its detection, Phys. Rev. D 58, 063001 (1998)."
LOWER_RESUME = re.compile(rf"^\s*\d{{1,3}}[.)]\s+(?:{RESUME_WORDS})\s+[a-z]")

CONTINUATION = re.compile(
    r"""^\s*\d{1,3}[.)]\s*(?:
          [:;,]                                  # "4. : 749-65."
        | \(\s*\d+\s*\)\s*[:;,]                 # "19 (1):54-9."
        | \d{1,4}\s*[-\u2013\u2014]\s*\d{1,4}\b    # a bare page range
        | \d{1,3}[.)]\s+[A-Z\u00c0-\u1ef9]         # "9. 29. De Souza" - two labels
        | (?:https?://|doi:|DOI:|PMID|PMCID)     # continuation furniture
      )""",
    re.X | re.I)

# A line that is nothing but a DOI or a DOI URL. a paper printed its DOI on
# its own line after a blank line, and NOISE's `https?://\S+$` branch deleted it
# before the continuation-merge below could reattach it -- so the reference was
# parsed with doi=None, fell back to a Crossref title search, and resolved to an
# unrelated dissertation. Bare DOI lines must survive NOISE and be merged.
BARE_DOI = re.compile(
    r"^\s*(?:https?://(?:dx\.)?doi\.org/|doi:\s*|DOI:\s*)?"
    r"(10\.\d{4,9}/\S+?)[.,;]?\s*$")


def _until_next_entry(lines, i, max_lines=12):
    """Line i joined with the lines after it, stopping before a line that
    starts an entry of its own -- so a running header of the paper's own
    authors ("Author, A. B., ... & Author, C. D.") cannot borrow the
    next reference's year. Up to 12 lines: justified text can put one word
    on each line ("Smith," / "S." / "(2022," / "July" / "24).")."""
    out = [lines[i]]
    for l in lines[i + 1:i + max_lines]:
        if (APA.match(l) or APA_X.match(l)) and not _MID_AUTHORS.search(out[-1]):
            break
        out.append(l)
    return " ".join(out)


# A line ending inside an author list ("Theta, T.," / "& ") is continued by
# the next line even when that line reads like an entry start on its own
# ("Iota, I., & Kappa, K. (2024). Title ...").
_MID_AUTHORS = re.compile(r"(?:[A-ZÀ-ỹ]\.\s*,|&|\band)\s*$")


def split_refs(tail, keep_markers=False):
    lines = [l.strip() for l in tail.split("\n")]
    lines = [l for l in lines if l and (BARE_DOI.match(l) or not NOISE.match(l))]
    lines = merge_lone_markers(lines)

    def _is_continuation(line):
        return bool(CONTINUATION.match(line)
                    or CONTINUATION_SPACED.match(line)
                    or LEADING_ISSUE.match(line)
                    or LOWER_RESUME.match(line)
                    or _is_numeric_row(line))

    # Count only lines that are genuinely numbered entries. A wrapped page
    # range such as "(2):378-390." looks like a marker to MARK; counting it
    # here flipped whole author-date bibliographies into numbered mode.
    _labelled = [l for l in lines
                 if MARK.match(l) and (MARK.match(l).group(4) or "").strip()
                 and not _is_continuation(l)]

    def _exactly_one_two(cands):
        """A 2-entry list labelled [1], [2] is a real bibliography."""
        if len(cands) != 2:
            return False
        got = []
        for l in cands:
            m = MARK.match(l)
            got.append(m.group(1) or m.group(2) or m.group(3))
        return got == ["1", "2"]

    # a paper appends its title page AFTER the reference heading, so the two
    # numbered author affiliations ("1. Faculty of ...") were the only labelled
    # lines and _exactly_one_two declared a 2-entry numbered bibliography --
    # discarding 18 real author-date entries. The shortcut is only safe when
    # author-date entries do not clearly outnumber the two labels.
    _authordate = sum(1 for l in lines
                      if APA.match(l) or HARV.match(l) or CHICAGO.match(l)
                      or AAS.match(l) or SEMI.match(l))
    numbered = len(_labelled) >= 3 or (
        _exactly_one_two(_labelled) and _authordate <= 2)

    named = sum(1 for l in lines if NAMED_MARK.match(l)) >= 3

    refs, cur = [], []
    for i, l in enumerate(lines):
        m = MARK.match(l)
        nm = NAMED_MARK.match(l)
        if named:
            starts = bool(nm)
        elif numbered:
            starts = bool(m and (m.group(4) or "").strip())
        else:
            starts = bool(APA.match(l) or HARV.match(l)
                          or CHICAGO.match(l) or AAS.match(l)
                          or SEMI.match(l) or APA_X.match(l))
            prev = lines[i - 1] if i else ""
            if starts and cur and _MID_AUTHORS.search(prev):
                starts = False
            if (not starts and AUTHOR_START.match(l)
                    and not re.search(r"(?:[,&]|\band)\s*$", prev)
                    and APA_LONG.match(_until_next_entry(lines, i))):
                starts = True
            # A page range wrapped as "74–" / "93." and merge_lone_markers
            # glued the "93." onto the next entry ("93. Li, S. (2010)."):
            # the number ends the previous entry and the author starts a new one.
            if (not starts and m and cur
                    and APA.match((m.group(4) or "").strip())):
                cur.append(l[:m.start(4)].strip())
                l = m.group(4).strip()
                starts = True
        if starts and BARE_DOI.match(l):
            starts = False
        # A wrapped continuation only looks like a new entry.
        if starts and not named and _is_continuation(l):
            starts = False
        if starts:
            if cur:
                refs.append(" ".join(cur))
            if named and nm:
                text = (nm.group(2) or "").strip()
                cur = [f"[{nm.group(1)}] {text}" if keep_markers else text]
            elif numbered and m:
                n = m.group(1) or m.group(2) or m.group(3)
                text = (m.group(4) or "").strip()
                cur = [f"{n}. {text}" if keep_markers else text]
            else:
                cur = [l]
        elif cur:
            cur.append(l)
    if cur:
        refs.append(" ".join(cur))

    refs = [re.sub(r"\s+", " ", r).strip() for r in refs]
    # A bare DOI/URL line continues the preceding reference; it is not a new one.
    merged = []
    for r in refs:
        if merged and (BARE_DOI.match(r) or re.fullmatch(
                r"(?:https?://\S+|doi:\s*\S+|10\.\d{4,9}/\S+)[.,;]?", r)):
            merged[-1] = merged[-1].rstrip("-\u2013\u2014 ") + " " + r
        else:
            merged.append(r)
    return [r for r in merged if len(r) > 40]


# Last resort for an unlabelled list whose entry starts none of the patterns
# above recognise . extract_refs calls it only when a heading
# was found and split_refs returned nothing, so a paper that parses today is
# never affected.
#   some papers  Harvard, a blank line between entries:
#                 "Adam, A, Josephson, P-EB & Lindahl, G 2017, 'Aggregation ...'"
#   a paper         "Abbas Z. 2020. Reassessing ... 10, 6: 404-410."
#   some papers  NeurIPS: "Iz Beltagy, Matthew E Peters, and Arman Cohan.
#                 Longformer ... arXiv:2004.05150, 2020."
# With no start pattern, entries are found by where they END: a line that
# closes on a year, a page/article number, a DOI, a URL or an ISBN, followed by
# a line opening with a capital.
UNLABELLED_END = re.compile(
    r"(?:\d[)\]]?|10\.\d{4,9}/\S+|https?://\S+|ISBN[\s\d-]+[\dX])[.]?\s*$")
APA_YEAR_END = re.compile(r"\(\d{4}[a-z]?\)\.?\s*$")
_YEAR = re.compile(r"\b(?:19[5-9]\d|20[0-4]\d)[a-z]?\b")
_MAX_ENTRY = 1200   # longer than any reference: prose or an appendix


# A line that opens an author list: "Muhammad Firoz Mridha, Aklima ...",
# "Rada Mihalcea and Paul Tarau." ACL entries end "... Computational
# Linguistics." with no digit, so UNLABELLED_END alone merged a paper.
NAME_START = re.compile(
    r"^(?:[A-Z\u00c0-\u1ef9][\w\u2019'\-]*\.?\s+){1,3}[A-Z\u00c0-\u1ef9][\w\u2019'\-]+(?:,|\s+and\s)")


def drop_repeated_lines(text):
    """Remove running headers/footers: a line printed on several pages (a paper
    title and conference line, an "Author, A., ... (2024)" citation
    header, which read as a reference of its own)."""
    raw = text.split("\n")
    counts = {}
    for l in raw:
        k = l.strip()
        if k:
            counts[k] = counts.get(k, 0) + 1
    furniture = {k for k, c in counts.items() if c >= 3 or (c >= 2 and len(k) > 30)}
    return "\n".join(l for l in raw if l.strip() not in furniture)


def split_unlabeled(tail):
    # NOISE drops a line that is only a URL (page footers); here it is most
    # often an entry's DOI or web address on its own line, so keep it.
    raw = [l for l in drop_repeated_lines(tail).split("\n")
           if not NOISE.match(l.strip()) or re.match(r"\s*(?:https?://|doi:|10\.\d)", l)]

    # 1. Blank-line paragraphs, when they are reference-sized and dated. A
    #    paragraph with no year is the rest of an entry cut by a page break.
    paras = [re.sub(r"\s+", " ", p).strip()
             for p in re.split(r"\n[ \t]*\n", "\n".join(raw))]
    paras = [p for p in paras if p]
    if len(paras) >= 5:
        lens = sorted(len(p) for p in paras)
        dated = sum(1 for p in paras if _YEAR.search(p))
        if lens[len(lens) // 2] <= 500 and dated >= 0.7 * len(paras):
            out = []
            for p in paras:
                if out and not _YEAR.search(p):
                    out[-1] += " " + p
                else:
                    out.append(p)
            return _leading_references(out)

    # 2. Split where an entry ends.
    lines = [l.strip() for l in raw if l.strip()]
    out, cur = [], []
    for i, l in enumerate(lines):
        cur.append(l)
        text = " ".join(cur)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        ends = (UNLABELLED_END.search(l) or (l.endswith(".") and NAME_START.match(nxt))
                # the tail of a URL broken across lines: "26_Report.pdf."
                or ("http" in text and re.fullmatch(r"\S+\.", l)))
        if APA_YEAR_END.search(l):
            ends = False   # "... & Willem, A. (2020)." -- the title follows
        if (ends and len(text) >= 60 and _YEAR.search(text)
                and (not nxt or re.match(r"[A-Z\u00c0-\u1ef9]", nxt))):
            out.append(text)
            cur = []
    if cur:
        out.append(" ".join(cur))
    return _leading_references(out)


def _leading_references(entries):
    """The entries up to the first that is not a reference (no year, or far
    too long): whatever follows the list -- an appendix, author bios -- ends it."""
    keep = []
    for e in entries:
        e = re.sub(r"\s+", " ", e).strip()
        if len(e) > _MAX_ENTRY or not _YEAR.search(e):
            break
        if len(e) > 40:
            keep.append(e)
    return keep if len(keep) >= 3 else []
