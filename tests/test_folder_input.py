from pathlib import Path

from faker import Faker

from pii_strip.cli import main
from tests.support.pdf_factory import IMAGE_PAGE, extract_text, make_mixed_pdf, make_pdf

fake = Faker("da_DK")
Faker.seed(11)


def _write_corrupt_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.7 this is not really a pdf")

    return path


def test_every_pdf_in_the_folder_is_redacted_into_processed(tmp_path):
    first, second = fake.email(), fake.email()
    make_pdf(tmp_path / "a.pdf", [f"Mail {first}"])
    make_pdf(tmp_path / "b.pdf", [f"Mail {second}"])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 0
    assert sorted(path.name for path in (tmp_path / "processed").iterdir()) == ["a-stripped.pdf", "b-stripped.pdf"]
    assert first not in extract_text(tmp_path / "processed" / "a-stripped.pdf")
    assert second not in extract_text(tmp_path / "processed" / "b-stripped.pdf")


def test_an_uppercase_extension_is_processed_and_written_in_lowercase(tmp_path):
    make_pdf(tmp_path / "Scan.PDF", ["Hello"])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 0
    assert (tmp_path / "processed" / "Scan-stripped.pdf").exists()


def test_subfolders_and_other_files_are_skipped_and_listed_and_hidden_files_are_skipped_silently(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    (tmp_path / "notes.txt").write_text("just text")
    (tmp_path / "old").mkdir()
    make_pdf(tmp_path / "old" / "nested.pdf", ["Hello"])
    (tmp_path / ".DS_Store").write_bytes(b"\x00")

    exit_code = main([str(tmp_path), "--quiet"])

    err = capsys.readouterr().err
    assert exit_code == 0
    assert [path.name for path in (tmp_path / "processed").iterdir()] == ["a-stripped.pdf"]
    assert "notes.txt" in err and "old" in err
    assert ".DS_Store" not in err


def test_the_processed_folder_is_not_listed_as_skipped_on_a_second_run(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    main([str(tmp_path), "--quiet"])
    capsys.readouterr()

    main([str(tmp_path), "--quiet", "--force"])

    assert "processed" not in capsys.readouterr().err


def test_an_existing_output_is_not_overwritten_without_force(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    output = tmp_path / "processed" / "a-stripped.pdf"
    output.parent.mkdir()
    output.write_bytes(b"keep me")

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 1
    assert output.read_bytes() == b"keep me"
    assert "--force" in capsys.readouterr().err


def test_force_overwrites_an_existing_output(tmp_path):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    output = tmp_path / "processed" / "a-stripped.pdf"
    output.parent.mkdir()
    output.write_bytes(b"old")

    exit_code = main([str(tmp_path), "--quiet", "--force"])

    assert exit_code == 0
    assert output.read_bytes() != b"old"


def test_a_corrupt_pdf_fails_only_that_file_and_names_it(tmp_path, capsys):
    _write_corrupt_pdf(tmp_path / "broken.pdf")
    make_pdf(tmp_path / "good.pdf", ["Hello"])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 1
    assert (tmp_path / "processed" / "good-stripped.pdf").exists()
    assert "broken.pdf: " in capsys.readouterr().err


def test_pii_left_in_one_output_wins_over_a_failed_file_and_image_pages(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    make_pdf(tmp_path / "a-leak.pdf", [f"Mail {fake.email()}"])
    _write_corrupt_pdf(tmp_path / "b-broken.pdf")
    make_mixed_pdf(tmp_path / "c-scan.pdf", [(IMAGE_PAGE, "Scanned letter")])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 2


def test_a_failed_file_wins_over_image_pages(tmp_path):
    _write_corrupt_pdf(tmp_path / "a-broken.pdf")
    make_mixed_pdf(tmp_path / "b-scan.pdf", [(IMAGE_PAGE, "Scanned letter")])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 1


def test_image_pages_in_one_file_exit_with_3(tmp_path):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    make_mixed_pdf(tmp_path / "b-scan.pdf", [(IMAGE_PAGE, "Scanned letter")])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 3


def test_output_is_not_allowed_with_a_folder(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])

    exit_code = main([str(tmp_path), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "-o" in capsys.readouterr().err
    assert not (tmp_path / "processed").exists()


def test_a_folder_without_pdfs_exits_with_1(tmp_path, capsys):
    (tmp_path / "notes.txt").write_text("just text")

    exit_code = main([str(tmp_path)])

    assert exit_code == 1
    assert "no pdf" in capsys.readouterr().err.lower()


def test_a_single_file_still_needs_an_output(tmp_path, capsys):
    source = make_pdf(tmp_path / "a.pdf", ["Hello"])

    exit_code = main([str(source)])

    assert exit_code == 1
    assert "-o" in capsys.readouterr().err


def test_the_summary_line_of_each_file_starts_with_its_name_and_a_final_line_counts_the_files(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    _write_corrupt_pdf(tmp_path / "b.pdf")

    main([str(tmp_path)])

    lines = capsys.readouterr().err.strip().splitlines()
    assert any(line.startswith("a.pdf: redacted") for line in lines)
    assert lines[-1].startswith("processed 2 files")
    assert "1 failed" in lines[-1]


def test_quiet_hides_the_final_line_when_every_file_is_clean(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])

    main([str(tmp_path), "--quiet"])

    assert capsys.readouterr().err == ""


def test_quiet_keeps_the_final_line_when_a_file_failed(tmp_path, capsys):
    _write_corrupt_pdf(tmp_path / "a.pdf")
    make_pdf(tmp_path / "b.pdf", ["Hello"])

    main([str(tmp_path), "--quiet"])

    assert "processed 2 files" in capsys.readouterr().err
