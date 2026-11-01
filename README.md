# References_Parser

Pulls the reference list out of an academic paper's PDF and splits it into
clean entries, one JSON object per reference.

It handles numbered lists (`[1]`, `1.`, `(1)`), author-date lists (APA,
Harvard, Chicago, AAAI), named labels (`[Smith et al., 2020]`), and lists with
no heading at all. It also deals with the usual PDF text-layer damage:
wrapped author lists, page ranges split across lines, running page headers,
author biographies or a second-language abstract printed after the list, and
Vietnamese headings ("Tài liệu tham khảo").

## Usage

```bash
pip install pymupdf          # optional; falls back to pdftotext (poppler)
python3 references_parser/parse_pdf.py paper.pdf -o references.json
```

Each entry looks like:

```json
{
  "n": 3,
  "raw": "Garrison, D. R., Anderson, T., & Archer, W. (2000). Critical inquiry ...",
  "printed_label": null,
  "title": "Critical inquiry in a text-based environment: ...",
  "year": 2000,
  "doi": "10.1016/s1096-7516(00)00016-6",
  "authors_raw": "Garrison, D. R., Anderson, T., & Archer, W.",
  "citation_style": "author_year",
  "contexts": ["...the sentence in the paper that cites it..."]
}
```

A one-line summary (`N refs | title N | doi N | contexts N`) goes to stderr.

From Python:

```python
from parse_pdf import parse, pdf_text
refs = parse(pdf_text("paper.pdf"))
```

## Files

| File | What it does |
|---|---|
| `parse_pdf.py` | Command line and `parse()`: PDF text, find the list, build the JSON |
| `parse_refs.py` | Reference headings, entry-start patterns, `split_refs()` |
| `extract_refs.py` | Fallbacks (lists with no heading), trailing-matter cuts, in-text citation contexts |
| `titleguess.py` | Title and DOI extraction from one reference string |

## Tests

```bash
python3 -m pytest tests/
```

Python 3.9 or later. No dependencies beyond the standard library, plus PyMuPDF
or `pdftotext` to read PDFs.
