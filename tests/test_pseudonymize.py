import json
import re
import uuid
from pathlib import Path

import pytest

from pii_strip.cli import main
from tests.support.pdf_factory import make_pdf

UUID_PDF = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.pdf$")


def _write_corrupt_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.7 this is not really a pdf")

    return path


def test_each_output_is_named_with_a_new_uuid(tmp_path):
    make_pdf(tmp_path / "574_838_Mette_Jensen.pdf", ["Hello"])
    make_pdf(tmp_path / "574_839_Lars_Nielsen.pdf", ["Hello"])

    main([str(tmp_path), "--quiet"])

    names = [path.name for path in (tmp_path / "processed").iterdir()]
    assert len(names) == 2 and all(UUID_PDF.match(name) for name in names)


def test_each_output_has_a_key_file_with_the_original_and_redacted_file_and_the_result(tmp_path):
    make_pdf(tmp_path / "574_838_Mette_Jensen.pdf", ["Hello"])

    main([str(tmp_path), "--quiet"])

    output = next((tmp_path / "processed").iterdir())
    key = (tmp_path / "keys" / f"{output.stem}.md").read_text()
    assert key.startswith(f"# {output.stem}\n")
    assert "- **Original file:** 574_838_Mette_Jensen.pdf\n" in key
    assert f"- **Redacted file:** processed/{output.name}\n" in key
    assert "- **Processed:** " in key
    assert "- **Result:** clean\n" in key
    assert "- **Candidate:** " in key


def test_a_failed_file_gets_a_key_but_no_output(tmp_path):
    _write_corrupt_pdf(tmp_path / "574_838_Mette_Jensen.pdf")

    main([str(tmp_path), "--quiet"])

    keys = list((tmp_path / "keys").glob("*.md"))
    assert len(keys) == 1
    assert "- **Result:** failed (1)\n" in keys[0].read_text()
    assert list((tmp_path / "processed").iterdir()) == []


def test_no_output_file_contains_the_original_file_name(tmp_path):
    make_pdf(tmp_path / "574_838_Mette_Jensen.pdf", ["Hello"])

    main([str(tmp_path), "--quiet"])

    output = next((tmp_path / "processed").iterdir())
    assert b"Mette_Jensen" not in output.read_bytes()


def test_a_second_run_replaces_the_earlier_results_without_force(tmp_path, capsys):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    main([str(tmp_path), "--quiet"])
    first_output = next((tmp_path / "processed").iterdir())
    capsys.readouterr()

    exit_code = main([str(tmp_path), "--quiet"])

    outputs = list((tmp_path / "processed").iterdir())
    assert exit_code == 0
    assert len(outputs) == 1 and outputs[0] != first_output
    assert len(list((tmp_path / "keys").iterdir())) == 1
    assert "deleted" in capsys.readouterr().err


def test_files_saved_into_the_output_folders_are_deleted_on_the_next_run(tmp_path):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed" / "notes.txt").write_text("old")
    (tmp_path / "keys").mkdir()
    (tmp_path / "keys" / "old.md").write_text("old")

    main([str(tmp_path), "--quiet"])

    assert not (tmp_path / "processed" / "notes.txt").exists()
    assert not (tmp_path / "keys" / "old.md").exists()


def test_nothing_outside_processed_and_keys_is_deleted(tmp_path):
    make_pdf(tmp_path / "a.pdf", ["Hello"])
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "keep.txt").write_text("keep")
    (tmp_path / "notes.txt").write_text("keep")

    main([str(tmp_path), "--quiet"])

    assert (tmp_path / "other" / "keep.txt").read_text() == "keep"
    assert (tmp_path / "notes.txt").read_text() == "keep"
    assert (tmp_path / "a.pdf").exists()


@pytest.mark.parametrize("folder", ["processed", "keys"])
def test_a_symbolic_link_named_like_an_output_folder_stops_the_run_before_deleting(tmp_path, folder, capsys):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("keep")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    make_pdf(inputs / "a.pdf", ["Hello"])
    (inputs / folder).symlink_to(elsewhere, target_is_directory=True)

    exit_code = main([str(inputs), "--quiet"])

    assert exit_code == 1
    assert (elsewhere / "keep.txt").read_text() == "keep"
    assert "link" in capsys.readouterr().err


def test_force_is_accepted_and_has_no_effect_with_a_folder(tmp_path):
    make_pdf(tmp_path / "a.pdf", ["Hello"])

    exit_code = main([str(tmp_path), "--quiet", "--force"])

    assert exit_code == 0


def test_the_folder_report_names_each_file_only_by_its_uuid(tmp_path):
    make_pdf(tmp_path / "574_838_Mette_Jensen.pdf", ["Hello"])
    _write_corrupt_pdf(tmp_path / "574_839_Lars_Nielsen.pdf")
    report = tmp_path / "report.json"

    main([str(tmp_path), "--report", str(report), "--quiet"])

    content = json.loads(report.read_text())
    assert "Mette_Jensen" not in report.read_text()
    assert "Lars_Nielsen" not in report.read_text()
    assert all("input" not in entry and uuid.UUID(entry["id"]) for entry in content["files"])
    assert content["files"][1]["error"] is not None
