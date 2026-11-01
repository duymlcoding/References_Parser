#!/usr/bin/env python3
"""Extract the reference list of an academic paper from its PDF, as JSON.

    python3 parse_pdf.py paper.pdf [-o references.json]

Text comes from PyMuPDF when it is installed, else from pdftotext (poppler);
the two can split a few lists slightly differently.
"""
import argparse, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_refs import (HDR, LIT_HDR, NAMED_MARK, YEAR, DOI_RE,  # noqa: E402
                          title_guess, strip_invisible, drop_repeated_lines,
                          split_unlabeled, parse_tail, _label_of,
                          find_headerless_bibliography,
                          find_bare_numbered_bibliography,
                          bare_labels_to_dotted, find_headerless_authordate,
                          superscript_citations, contexts_for,
                          _has_numeric_citation, _first_author_surname,
                          authors_raw)


def pdf_text(pdf):
    """Plain text of the PDF, de-hyphenated as init_paper.to_md does."""
    try:
        import pymupdf
        doc = pymupdf.open(pdf)
        pages = [pg.get_text("text") for pg in doc]
        doc.close()
    except ImportError:
        if not shutil.which("pdftotext"):
            sys.exit("need PyMuPDF (pip install pymupdf) or pdftotext (brew install poppler)")
        txt = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf, "-"],
                             capture_output=True, text=True, check=True).stdout
        pages = txt.split("\f")
    text = "".join("\n\n" + t for t in pages)
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def parse(plain):
    """Reference entries of a paper's plain text."""
    hits = list(HDR.finditer(plain))
    refs, body, tail = [], plain, None
    if hits:
        cut = hits[-1]
        body, tail = plain[:cut.start()], plain[cut.end():]
        refs, tail = parse_tail(tail)
        if 1 <= len(refs) <= 2:
            for h in reversed(hits[:-1]):
                r2, t2 = parse_tail(plain[h.end():])
                if (len(r2) >= 5 and len(r2) >= 3 * len(refs)
                        and _label_of(r2[0]) == 1 and _label_of(r2[1]) == 2):
                    body, tail, refs = plain[:h.start()], t2, r2
                    break
        if refs and all(_label_of(r) is None for r in refs):
            alt = split_unlabeled(tail)
            if len(alt) > len(refs):
                refs = alt
    if not refs:
        pos = find_headerless_bibliography(plain)
        bare = False
        if pos is None and not hits:
            lit = list(LIT_HDR.finditer(plain))
            if lit:
                cut = lit[-1]
                body, tail = plain[:cut.start()], plain[cut.end():]
                refs, tail = parse_tail(tail)
        if pos is None and not refs:
            pos = find_bare_numbered_bibliography(plain)
            bare = pos is not None
        headerless = False
        end = None
        if pos is None and tail is None:
            span = find_headerless_authordate(plain)
            if span:
                pos, end = span
                headerless = True
        if pos is None and tail is None:
            raise SystemExit("NO REFERENCE HEADER FOUND")
        if pos is not None:
            body, tail = plain[:pos], plain[pos:end]
            if headerless:
                tail = drop_repeated_lines(tail)
            refs, tail = parse_tail(bare_labels_to_dotted(tail) if bare else tail)
            if headerless:
                alt = split_unlabeled(tail)
                if len(alt) > len(refs):
                    refs = alt
    if not refs and tail is not None:
        refs = split_unlabeled(tail)

    sup = superscript_citations(body, len(refs))
    out = []
    for i, r in enumerate(refs, 1):
        label = None
        lm = re.match(r"^\s*(?:\[\s*(\d{1,3})\s*\.?\s*\]|\(\s*(\d{1,3})\s*\)|(\d{1,3})[.)])\s*", r)
        if lm:
            label = int(lm.group(1) or lm.group(2) or lm.group(3))
        named_label = None
        if label is None:
            nm = NAMED_MARK.match(r)
            if nm:
                named_label = nm.group(1).strip()
        n = label if label is not None else i
        raw_no_label = re.sub(r"^\s*(?:\[\s*\d{1,3}\s*\.?\s*\]|\(\s*\d{1,3}\s*\)|\d{1,3}[.)])\s*", "", r, count=1)
        t = title_guess(raw_no_label)
        dm = DOI_RE.search(strip_invisible(raw_no_label).replace("\xad", ""))
        ys = YEAR.findall(raw_no_label)
        ctx = contexts_for(body, n, t, raw=raw_no_label,
                           year=int(ys[0]) if ys else None)
        if label is not None and not ctx and sup.get(n):
            ctx = sup[n]
        numeric = label is not None and (_has_numeric_citation(body, n) or bool(sup.get(n)))
        author_year = bool(not numeric and _first_author_surname(raw_no_label)
                           and ys and ctx)
        out.append({
            "n": n,
            "raw": r,
            "printed_label": label if label is not None else named_label,
            "title": t,
            "year": int(ys[0]) if ys else None,
            "doi": dm.group(0).rstrip(".,;") if dm else None,
            "authors_raw": authors_raw(raw_no_label, t),
            "citation_style": "numeric" if numeric else ("author_year" if author_year else "unknown"),
            "contexts": ctx,
        })
    if len({r["n"] for r in out}) != len(out):
        for i, r in enumerate(out, 1):
            r["n"] = i
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", help="write JSON here (default: stdout)")
    a = ap.parse_args()
    out = parse(pdf_text(a.pdf))
    js = json.dumps(out, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
    else:
        print(js)
    print(f"{len(out)} refs | title {sum(1 for x in out if x['title'])} | "
          f"doi {sum(1 for x in out if x['doi'])} | "
          f"contexts {sum(1 for x in out if x['contexts'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
