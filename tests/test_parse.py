"""Regression tests on made-up reference lists (no real papers)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "references_parser"))
from parse_pdf import parse  # noqa: E402


def refs(text):
    return [r["raw"] for r in parse(text)]


BODY = "Introduction\nPrior work (Alpha, 2015; Beta, 2020) studied this.\n\n"


def test_numbered_list():
    out = parse(BODY + "References\n[1] A. Alpha, A first title, J. Test 1 (2015) 1-2.\n"
                "[2] B. Beta, A second title, J. Test 2 (2020) 3-4.\n"
                "[3] C. Gamma, A third title, J. Test 3 (2021) 5-6.\n")
    assert [r["n"] for r in out] == [1, 2, 3]


def test_dated_items_start_new_entries():
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Beta, B. (2020, January). A conference paper. In Proceedings of Testing (pp. 5-6).\n"
               "Gamma, C. (2022, July 24). A web page. Example Site.\n"
               "Delta, D. (n.d.). About us. https://example.org/about\n")
    assert len(got) == 4


def test_editor_parenthesis_and_particle_and_corporate_author():
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Beta, B., & Gamma, C. (Eds.). (2017). An edited book. Publisher.\n"
               "van der Delta, D. (2019). A Dutch surname. Journal of Tests, 3, 1-9.\n"
               "Example-Corp. (2025). Annual report. https://example.com\n")
    assert len(got) == 4


def test_author_list_wrapping_before_year():
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Beta, B., Gamma, C., Delta, D., Epsilon, E., Zeta, Z., Eta, E., Theta, T.,\n"
               "Iota, I., & Kappa, K. (2024). A long author list. Journal of Tests, 9, 1-2.\n"
               "Lambda, L. (2020). Another title. Journal of Tests, 4, 5-6.\n")
    assert len(got) == 3
    assert got[1].startswith("Beta") and "Kappa" in got[1]


def test_biodata_and_second_abstract_are_cut():
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Beta, B. (2020). A second title. Journal of Tests, 2, 5-6.\n"
               "Gamma, C. (2021). A third title. Journal of Tests, 3, 7-8.\n"
               "Biodata\n"
               "Alpha Author is a lecturer at an example university.\n")
    assert len(got) == 3 and "lecturer" not in got[-1]
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Beta, B. (2020). A second title. Journal of Tests, 2, 5-6.\n"
               "Gamma, C. (2021). A third title. Journal of Tests, 3, 7-8.\n"
               "MỘT TIÊU ĐỀ TIẾNG VIỆT\n"
               "Tóm tắt: Bài báo này mô tả một nghiên cứu.\n")
    assert len(got) == 3 and "Tóm tắt" not in got[-1]


def test_issn_running_header_is_dropped():
    got = refs(BODY + "References\n"
               "Alpha, A. (2015). A first title. Journal of Tests, 1(2), 3-4.\n"
               "Example Journal (2025), 25(8), 12-17 ISSN: 1234-5678\n"
               "Beta, B. (2020). A second title. Journal of Tests, 2, 5-6.\n"
               "Gamma, C. (2021). A third title. Journal of Tests, 3, 7-8.\n")
    assert len(got) == 3 and all("ISSN" not in r for r in got)
