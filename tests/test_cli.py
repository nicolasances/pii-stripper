import json

import pytest
from faker import Faker

from pii_strip import __version__
from pii_strip.cli import main
from tests.support.pdf_factory import IMAGE_PAGE, EMPTY_PAGE, extract_text, make_encrypted_pdf, make_mixed_pdf, make_pdf

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


def test_an_unsupported_language_exits_with_1(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--lang", "fr"])

    assert exit_code == 1
    assert "fr" in capsys.readouterr().err


def test_an_unknown_entity_exits_with_1(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "CREDIT_CARD"])

    assert exit_code == 1
    assert "CREDIT_CARD" in capsys.readouterr().err


def test_a_missing_model_exits_with_1_and_explains_how_to_install(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("pii_strip.nlp.spacy.util.is_package", lambda name: False)
    source = make_pdf(tmp_path / "in.pdf", ["hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "pip install" in capsys.readouterr().err


def test_cli_redacts_english_and_danish_names(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Mary Johnson signed the letter yesterday.", "Mette Hansen har underskrevet brevet i går."])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output)])

    text = extract_text(output)
    assert exit_code == 0
    assert "Mary Johnson" not in text
    assert "Mette Hansen" not in text


def test_entities_flag_restricts_what_is_redacted(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Mary Johnson wrote to mary@example.com"])
    output = tmp_path / "out.pdf"

    main([str(source), "-o", str(output), "--entities", "EMAIL_ADDRESS"])

    text = extract_text(output)
    assert "mary@example.com" not in text
    assert "Mary Johnson" in text


def test_a_missing_deny_file_exits_with_1_and_names_the_file(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--deny", str(tmp_path / "nope.txt")])

    assert exit_code == 1
    assert "nope.txt" in capsys.readouterr().err
    assert not (tmp_path / "out.pdf").exists()


def test_a_missing_allow_file_exits_with_1_and_names_the_file(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--allow", str(tmp_path / "nope.txt")])

    assert exit_code == 1
    assert "nope.txt" in capsys.readouterr().err


@pytest.mark.parametrize("threshold", ["1.5", "-1", "high"])
def test_an_invalid_threshold_exits_with_1(tmp_path, capsys, threshold):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--threshold", threshold])

    assert exit_code == 1
    assert "threshold" in capsys.readouterr().err.lower()


def test_the_deny_file_makes_the_cli_redact_a_term(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Projektet hedder kolibri og er hemmeligt."])
    deny = tmp_path / "deny.txt"
    deny.write_text("# secret names\nkolibri\n", encoding="utf-8")
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--deny", str(deny)])

    assert exit_code == 0
    assert "kolibri" not in extract_text(output)


def test_the_allow_file_makes_the_cli_keep_a_term(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["Skriv til info@acme.dk i dag"])
    allow = tmp_path / "allow.txt"
    allow.write_text("INFO@acme.dk\n", encoding="utf-8")
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--allow", str(allow)])

    assert exit_code == 0
    assert "info@acme.dk" in extract_text(output)


def test_the_threshold_flag_reaches_the_detector(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", ["tlf. 12345678"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--threshold", "0.99"])

    assert exit_code == 0
    assert "12345678" in extract_text(output)


def test_cli_removes_bookmarks_by_default_and_keeps_them_with_keep_outline(tmp_path):
    from tests.support.pdf_factory import HIDDEN_PII, make_hidden_pii_pdf
    import pymupdf

    source = make_hidden_pii_pdf(tmp_path / "in.pdf")
    removed = tmp_path / "removed.pdf"
    kept = tmp_path / "kept.pdf"

    assert main([str(source), "-o", str(removed)]) == 0
    assert main([str(source), "-o", str(kept), "--keep-outline"]) == 0

    removed_doc = pymupdf.open(removed)
    kept_doc = pymupdf.open(kept)
    assert removed_doc.get_toc() == []
    assert [entry[1] for entry in kept_doc.get_toc()] == [HIDDEN_PII["bookmark"]]


def test_a_clean_run_exits_with_0_and_reports_no_residuals(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf")])

    assert exit_code == 0
    assert "not clean" not in capsys.readouterr().err


def test_a_failed_redaction_exits_with_2_and_names_what_is_left_without_leaking_it(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", ["Nothing here", f"Write to {email} please"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "not clean" in err
    assert "EMAIL_ADDRESS on page 2" in err
    assert email not in err


def test_the_output_is_kept_when_verification_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--entities", "EMAIL_ADDRESS"])

    assert exit_code == 2
    assert output.exists()


def test_a_detected_string_the_redaction_search_misses_is_reported_as_left(tmp_path, capsys):
    """Known limitation (F01): a name typeset with a wide gap is detected, but the search on the page finds no area for it."""
    source = make_pdf(tmp_path / "in.pdf", ["Kontakt Zyxwv     Qrstu i dag"])
    deny = tmp_path / "deny.txt"
    deny.write_text("Zyxwv Qrstu\n", encoding="utf-8")
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--entities", "EMAIL_ADDRESS", "--deny", str(deny)])

    assert exit_code == 2
    assert "DENY_LIST on page 1" in capsys.readouterr().err
    assert output.exists()


def test_an_image_only_page_is_named_in_a_warning_and_exits_with_3(tmp_path, capsys):
    source = make_mixed_pdf(tmp_path / "in.pdf", ["First text page", "Second text page", (IMAGE_PAGE, f"Scanned letter to {fake.email()}")])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--entities", "EMAIL_ADDRESS"])

    err = capsys.readouterr().err
    assert exit_code == 3
    assert "image-only" in err
    assert "page 3" in err
    assert output.exists()


def test_allow_image_pages_exits_with_0_and_still_warns(tmp_path, capsys):
    source = make_mixed_pdf(tmp_path / "in.pdf", ["First text page", "Second text page", (IMAGE_PAGE, "Scanned page")])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--allow-image-pages"])

    assert exit_code == 0
    assert "page 3" in capsys.readouterr().err


def test_an_empty_page_does_not_warn_or_change_the_exit_code(tmp_path, capsys):
    source = make_mixed_pdf(tmp_path / "in.pdf", ["Text page", EMPTY_PAGE])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS"])

    assert exit_code == 0
    assert "image-only" not in capsys.readouterr().err


def test_pii_left_in_the_output_exits_with_2_even_with_image_only_pages(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    source = make_mixed_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please", (IMAGE_PAGE, "Scanned page")])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "image-only" in err


def test_a_summary_line_is_printed_on_stderr_by_default(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])

    main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS"])

    captured = capsys.readouterr()
    assert "redacted 1 item on 1 page (EMAIL_ADDRESS 1)" in captured.err
    assert "verification OK" in captured.err
    assert captured.out == ""


def test_quiet_suppresses_the_summary_line(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--quiet"])

    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_quiet_still_prints_warnings_and_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    source = make_mixed_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please", (IMAGE_PAGE, "Scanned page")])

    main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--quiet"])

    err = capsys.readouterr().err
    assert "image-only" in err
    assert "not clean" in err
    assert "verification" not in err


def test_report_writes_a_json_file_with_every_section(tmp_path):
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])
    report_path = tmp_path / "findings.json"

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--report", str(report_path)])

    report = json.loads(report_path.read_text())
    assert set(report) == {"schema_version", "tool", "run", "configuration", "findings", "image_only_pages", "sanitize", "verification", "exit_code"}
    assert report["exit_code"] == exit_code == 0
    assert report["configuration"]["entities"] == ["EMAIL_ADDRESS"]
    assert [finding["entity_type"] for finding in report["findings"]] == ["EMAIL_ADDRESS"]


def test_the_report_holds_none_of_the_pii_by_default(tmp_path):
    email = fake.email()
    name = "Margaret Thompson"
    cpr = "010190-1234"
    deny_term = "Bluebird"
    deny_file = tmp_path / "deny.txt"
    deny_file.write_text(deny_term)
    source = make_pdf(tmp_path / "in.pdf", [f"{name} wrote to {email} about project {deny_term}.", f"CPR {cpr} er oplyst."])
    report_path = tmp_path / "findings.json"

    main([str(source), "-o", str(tmp_path / "out.pdf"), "--deny", str(deny_file), "--report", str(report_path)])

    content = report_path.read_text()
    assert {"EMAIL_ADDRESS", "PERSON", "DK_CPR", "DENY_LIST"} <= {finding["entity_type"] for finding in json.loads(content)["findings"]}
    for pii in (email, name, "Margaret", "Thompson", cpr, "0101901234", deny_term):
        assert pii not in content


def test_a_report_is_written_when_pii_is_left_and_the_exit_code_is_2(tmp_path, monkeypatch):
    monkeypatch.setattr("pii_strip.redactor._whole_word_hits", lambda page, pii, words: [])
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])
    report_path = tmp_path / "findings.json"

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--report", str(report_path)])

    report = json.loads(report_path.read_text())
    assert exit_code == report["exit_code"] == 2
    assert report["verification"] == {"status": "failed", "residuals": [{"entity_type": "EMAIL_ADDRESS", "page": 1}]}


def test_a_report_is_written_with_the_image_only_pages_and_the_exit_code_3(tmp_path):
    source = make_mixed_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please", (IMAGE_PAGE, "Scanned page")])
    report_path = tmp_path / "findings.json"

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--report", str(report_path)])

    report = json.loads(report_path.read_text())
    assert exit_code == report["exit_code"] == 3
    assert report["image_only_pages"] == [2]


def test_no_report_is_written_when_the_run_fails_before_processing(tmp_path):
    report_path = tmp_path / "findings.json"

    exit_code = main([str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "out.pdf"), "--report", str(report_path)])

    assert exit_code == 1
    assert not report_path.exists()


def test_the_report_may_not_be_the_input_or_the_output_file(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", ["Hello"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--report", str(tmp_path / "out.pdf")])

    assert exit_code == 1
    assert "report" in capsys.readouterr().err.lower()


def test_a_report_that_cannot_be_written_exits_with_1(tmp_path, capsys):
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {fake.email()} please"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf"), "--entities", "EMAIL_ADDRESS", "--report", str(tmp_path / "missing-folder" / "findings.json")])

    assert exit_code == 1
    assert "report" in capsys.readouterr().err.lower()
