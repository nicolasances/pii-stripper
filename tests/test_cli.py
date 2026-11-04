import pytest
from faker import Faker

from pii_strip import __version__
from pii_strip.cli import main
from tests.support.pdf_factory import extract_text, make_encrypted_pdf, make_pdf

fake = Faker("da_DK")
Faker.seed(99)


def test_cli_redacts_the_input_into_the_output_file(tmp_path, capsys):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {email} please"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output)])

    assert exit_code == 0
    assert email not in extract_text(output)


def test_a_missing_input_file_exits_with_1_and_explains(tmp_path, capsys):
    exit_code = main([str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_a_file_that_is_not_a_pdf_exits_with_1(tmp_path, capsys):
    not_a_pdf = tmp_path / "notes.txt"
    not_a_pdf.write_text("just some text")

    exit_code = main([str(not_a_pdf), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "not a pdf" in capsys.readouterr().err.lower()


def test_a_corrupt_pdf_exits_with_1(tmp_path, capsys):
    corrupt = tmp_path / "broken.pdf"
    corrupt.write_bytes(b"%PDF-1.7 this is not really a pdf")

    exit_code = main([str(corrupt), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert capsys.readouterr().err != ""


def test_an_encrypted_pdf_exits_with_1_and_says_why(tmp_path, capsys):
    encrypted = make_encrypted_pdf(tmp_path / "locked.pdf", "secret")

    exit_code = main([str(encrypted), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "encrypted" in capsys.readouterr().err.lower()
    assert not (tmp_path / "out.pdf").exists()


def test_an_output_path_that_cannot_be_written_exits_with_1(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "missing-folder" / "out.pdf")])

    assert exit_code == 1
    assert capsys.readouterr().err != ""


def test_the_output_may_not_be_the_input_file(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Mail {fake.email()}"])
    before = source.read_bytes()

    exit_code = main([str(source), "-o", str(source)])

    assert exit_code == 1
    assert "same file" in capsys.readouterr().err.lower()
    assert source.read_bytes() == before


def test_an_existing_output_is_refused_without_force(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Mail {fake.email()}"])
    existing = make_pdf(tmp_path / "out.pdf", ["keep me"])
    before = existing.read_bytes()

    exit_code = main([str(source), "-o", str(existing)])

    assert exit_code == 1
    assert "--force" in capsys.readouterr().err
    assert existing.read_bytes() == before


def test_an_existing_output_is_overwritten_with_force(tmp_path):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"Mail {email}"])
    existing = make_pdf(tmp_path / "out.pdf", ["old content"])

    exit_code = main([str(source), "-o", str(existing), "--force"])

    assert exit_code == 0
    text = extract_text(existing)
    assert "old content" not in text
    assert email not in text


def test_a_usage_error_exits_with_1_not_2(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source)])

    assert exit_code == 1
    assert "-o" in capsys.readouterr().err


def test_version_prints_the_version(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--version"])

    assert stop.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_says_the_tool_is_assistive_and_not_a_guarantee(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])

    assert stop.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "not a guarantee" in output
    assert "review" in output
