"""Title extraction from a raw reference string.

Handles the styles actually present in this corpus:
  APA          Nguyen, T. V. (2023). Title here. Journal, 1(2), 3-4.
  Harvard      Aguilera, D.A., Perez, A., 2011. Title here. Appl. Catal. 104, 144.
  dash         Santos V. P., Marques N. S. S. - Title here, J. Appl. 12, 3.
  semicolon    Saji, S.; Hebden, A.; Du, C. Title here. Sustainability 2022, 14, 5181.
  quoted       Ajiboye, B. O., and H. O. Oloyede. 2018. “Title Here.” Journal 1: 2.
               G. Deng, O. Sheng, et al., “Title Here,” Journal 3 (2020): 4.
  Wiley book   Anandharamakrishnan, C. 2015. Title Here. John Wiley & Sons.
  initials     C. Zhang, X. Chen, H.P. Too, Title here, Springer. (Jul. 01, 2020).
"""
import re

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+\b")
INITIALS = re.compile(r"^(?:[A-ZÀ-ỹ][\w’'\-]*\s*,?\s*(?:[A-ZÀ-ỹ]\.\s*)+[;,]?\s*)+")

# Zero-width characters some publishers put between every letter of a DOI URL
# ("​h​t​t​p​s..."), with stray spaces beside
# them. They hide the URL from every pattern here, so it was read as the title.
# Only runs of three or more are touched: a lone one inside a title
# ("Self-​Determination") must stay, or the title stops being a
# substring of raw. A space after one is dropped only when the URL continues
# ("1​0​ 6"), not before the next word ("183657​ Chen").
_ZW = "[​-‍⁠﻿]"
_ZW_RUN = re.compile(rf"(?:[^\s​-‍⁠﻿]+[ \t]*{_ZW}[ \t]*){{3,}}")
_ZW_JOIN = re.compile(rf"{_ZW}[ \t]+(?=[0-9a-z./:_-])")


def strip_invisible(s):
    s = s or ""
    out, last = [], 0
    for m in _ZW_RUN.finditer(s):
        a, b = m.span()
        # One character past the run, so the lookahead sees what the last
        # space leads into ("20070​ 0481").
        seg = _ZW_JOIN.sub("", s[a:b + 1])
        seg = seg[:-1] if b < len(s) else seg
        out.append(s[last:a] + re.sub(_ZW, "", seg))
        last = b
    return "".join(out) + s[last:]


# A title printed in quotes right after the author block or the year (Wiley,
# IEEE, Chicago). The opening quote must follow ". " / ", " / ": " so a quoted
# phrase inside an APA title ("The “new normal” in ...") is not taken. After
# an APA "(2020)." the quote opens the title itself ("“It’s not like that at
# all”: A poststructuralist ..."), so APA is left to _candidates. The
# title's own closing punctuation sits inside the quotes (“Title.” / “Title,”);
# a quoted phrase that opens a title does not ("“Let’s accept it”: ...").
_QUOTED = re.compile(r"(?:^|(?<!\))[.,:]\s*)[“\"]([^”\"]{15,300}?)([.,?!])[”\"]")
_APA_YEAR = re.compile(r"\(\d{4}[a-z]?\)")

# Given-name-first authors, comma-separated, then the title (Elsevier/ACS
# without quotes): "C. Zhang, X. Chen, H.P. Too, Title, Venue ...".
_NAME_INIT_FIRST = r"(?:[A-ZÀ-ỹ]\.\s?-?)+\s?[A-ZÀ-ỹ][\w’'\-]+"
_INIT_FIRST_AUTHORS = re.compile(
    rf"^(?:(?:and\s+)?{_NAME_INIT_FIRST}(?:\s+et\s+al\.)?\s*,\s*)+")
# The venue that follows such a title: ", Venue Abbrev, 26(3)" or ", Springer. (Jul. 01".
_INIT_FIRST_VENUE = re.compile(r",\s+(?=[^,]{2,80}?(?:,\s*|\s)\(?\d)")


_AFTER_DOI = re.compile(
    r"((?:https?://\S*?doi\S*|doi:\s*\S+|\b10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)[.,;]?)\s+\S.*$",
    re.S)


def _truncate_at_doi(s):
    """Drop trailing matter that follows the reference's own DOI/URL."""
    m = _AFTER_DOI.search(s)
    return s[:m.start(1)] if m else s


def _clean(s):
    s = _truncate_at_doi(strip_invisible(s))
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\bdoi:\s*\S+", " ", s, flags=re.I)
    s = DOI_RE.sub(" ", s)
    s = re.sub(r"\[(CrossRef|PubMed|Google Scholar)\]", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def _candidates(s):
    """Yield the text remaining after each recognised author-block pattern."""
    # APA:  ... (2023). Title
    m = re.search(r"\(\d{4}[a-z]?\)\.?\s*(.+)", s)
    if m:
        yield m.group(1)
    # Harvard:  ... , 2011. Title
    m = re.search(r",\s*\d{4}[a-z]?\.\s*(.+)", s)
    if m:
        yield m.group(1)
    # Wiley/Chicago author-date:  Surname, C. 2015. Title
    # The year must follow an initial: "Title. 2016. Available at ..." puts
    # the year after the title.
    m = re.search(r"(?:\b[A-ZÀ-ỹ]\.|\bet al\.)\s+(?:19|20)\d{2}[a-z]?\.\s+(.+)", s)
    if m:
        yield m.group(1)
    # dash-separated:  Authors - Title, Journal
    m = re.search(r"\s[–—-]\s+(.+)", s)
    if m:
        yield m.group(1)
    # semicolon authors then title:  A.; B.; C. Title. Venue
    m = INITIALS.match(s)
    if m and m.end() < len(s):
        yield s[m.end():]
    yield s



_LEAD_JUNK = re.compile(r"^\s*\d{1,4}\s*[-\u2013]\s*\d{1,4}\s*[.,]?\s*")   # "205-214. "
_TRAIL_PAGE = re.compile(r"\s*(?:\u2026|\.\.\.)?\s*\d{1,4}\s*$")            # trailing page no.
_NAME_DASH = re.compile(
    r"^(?:[A-ZÀ-ỹ][\w’'\-]*\s+(?:[A-ZÀ-ỹ]\.\s*)*[A-ZÀ-ỹ]?\.?,?\s*){1,8}[\u2013\u2014-]\s*")


def _scrub(t):
    if not t:
        return t
    t = _LEAD_JUNK.sub("", t)
    t = _TRAIL_PAGE.sub("", t)
    m = _NAME_DASH.match(t)
    if m and len(t) - m.end() > 20:
        t = t[m.end():]
    return t.strip(" .,;\u2013\u2014-")


def _quoted(s):
    """A title printed in quotes after the author block or year, or None."""
    m = _QUOTED.search(s)
    if not m or _APA_YEAR.search(s, 0, m.start()):
        # After an APA year the title is unquoted; a later quote belongs to
        # another entry merged into this raw.
        return None
    t = m.group(1).strip(" ,.")
    return t + m.group(2) if m.group(2) in "?!" else t


def _after_initials_first_authors(s):
    """The text after a given-name-first author list, cut at the venue."""
    m = _INIT_FIRST_AUTHORS.match(s)
    if not m or len(s) - m.end() <= 15:
        return None
    rest = s[m.end():]
    v = _INIT_FIRST_VENUE.search(rest)
    return rest[:v.start()] if v else rest


def title_guess(ref, minlen=15, maxlen=300):
    s = _clean(ref)
    q = _quoted(s)
    if q and len(q) >= minlen:
        # The quotes delimit the title: splitting at "?" or ";" would cut it,
        # and _scrub would take "Sunfower Honey- —" for a name or a
        # closing "COVID-19" for a page number.
        return q[:maxlen]
    first = _after_initials_first_authors(s)
    best = None
    for cand in ([first] if first else []) + list(_candidates(s)):
        # cut at the first delimiter that ends a title
        parts = re.split(r"(?<=[a-z])\.\s+|\?\s+|;\s+|,\s*(?=(?:J\.|Journal|Int\.|Appl\.))", cand)
        parts = [p.strip(" .,;–—-") for p in parts if len(p.strip()) > minlen]
        if not parts:
            continue
        # a title is normally the first substantial segment, not the longest
        pick = parts[0]
        # reject segments that are obviously a venue/publisher tail
        if re.match(r"^(In|Ed[s]?\.|Publish|Press|Springer|Elsevier|CRC)\b", pick):
            pick = parts[1] if len(parts) > 1 else pick
        if best is None or len(pick) > len(best):
            best = pick
        # the first candidate pattern that matched is the most reliable
        break
    best = _scrub(best)
    return best[:maxlen] if best and len(best) >= minlen else None
