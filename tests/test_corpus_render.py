from bs4 import BeautifulSoup

from vigie.corpus.render import css_classes, normalize, render, word_count


def test_normalize_collapses_no_break_and_invisible_spaces() -> None:
    raw = "1.   Les entités financières\u200b\ufeff gèrent\n"
    assert normalize(raw) == "1. Les entités financières gèrent"


def test_css_classes_accepts_both_parsed_forms() -> None:
    tag = BeautifulSoup('<p class="oj-normal oj-bold">x</p>', "html.parser").p
    assert tag is not None
    assert css_classes(tag) == ["oj-normal", "oj-bold"]
    tag["class"] = "oj-note"
    assert css_classes(tag) == ["oj-note"]
    del tag["class"]
    assert css_classes(tag) == []


def test_two_cell_row_with_a_long_first_cell_is_a_data_row() -> None:
    table = BeautifulSoup(
        "<table><tr><td>Catégorie de client</td><td>risque élevé</td></tr>"
        "<tr><td>a)</td><td></td></tr></table>",
        "html.parser",
    ).table
    assert table is not None
    assert render(table) == ["Catégorie de client | risque élevé", "a)"]


def test_word_count_spans_lines() -> None:
    assert word_count(["un deux", "trois"]) == 3
