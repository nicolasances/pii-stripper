import pytest

from pii_strip.term_lists import parse_threshold, read_term_list


def test_reads_one_term_per_line(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("Zyxwv Qrstu\nACME\n", encoding="utf-8")

    assert read_term_list(path) == ["Zyxwv Qrstu", "ACME"]


def test_ignores_blank_lines_and_comments(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("# names\n\nACME\n   \n# DR\n", encoding="utf-8")

    assert read_term_list(path) == ["ACME"]


def test_trims_whitespace_around_terms(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("  ACME \t\n", encoding="utf-8")

    assert read_term_list(path) == ["ACME"]


def test_reads_utf8_terms(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("Søren Ærø\n", encoding="utf-8")

    assert read_term_list(path) == ["Søren Ærø"]


def test_a_missing_file_raises_a_value_error_naming_the_file(tmp_path):
    with pytest.raises(ValueError, match="nope.txt"):
        read_term_list(tmp_path / "nope.txt")


def test_a_file_that_is_not_utf8_raises_a_value_error(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_bytes(b"\xff\xfe\x00bad")

    with pytest.raises(ValueError, match="terms.txt"):
        read_term_list(path)


def test_the_default_threshold_is_0_5():
    assert parse_threshold(None) == 0.5


@pytest.mark.parametrize("value, expected", [("0", 0.0), ("0.6", 0.6), ("1", 1.0)])
def test_accepts_thresholds_from_0_to_1(value, expected):
    assert parse_threshold(value) == expected


@pytest.mark.parametrize("value", ["1.1", "-0.1", "abc", "", "nan"])
def test_rejects_thresholds_outside_0_to_1_or_not_a_number(value):
    with pytest.raises(ValueError, match="threshold"):
        parse_threshold(value)
