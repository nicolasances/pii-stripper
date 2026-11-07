import math
import shutil
from datetime import datetime
from pathlib import Path

from pii_strip.redactor import Finding

PROCESSED_FOLDER = "processed"
KEYS_FOLDER = "keys"
UNKNOWN_CANDIDATE = "unknown"
PERSON = "PERSON"
MIN_FULL_NAME_WORDS = 2
_RESULTS = {0: "clean", 2: "personal data left (2)", 3: "image-only pages (3)", 1: "failed (1)"}


class OutputFolderError(Exception):
    """The output folders can't be reset. The message is safe to show."""


def reset_output_folders(folder: Path) -> list[Path]:
    """Delete and recreate processed/ and keys/ directly inside the folder, and return the ones that existed. Nothing else is ever deleted.
    A symbolic link or a file with one of those names fails before anything is deleted, so the deletion can't reach outside the folder."""
    paths = [folder / PROCESSED_FOLDER, folder / KEYS_FOLDER]

    for path in paths:
        if path.is_symlink():
            raise OutputFolderError(f"{path} is a symbolic link; remove it, pii-strip only deletes real folders")

        if path.exists() and not path.is_dir():
            raise OutputFolderError(f"{path} is not a folder; remove or rename it")

    existing = [path for path in paths if path.exists()]

    try:
        for path in existing:
            shutil.rmtree(path)

        for path in paths:
            path.mkdir()
    except OSError as error:
        raise OutputFolderError(f"cannot reset the output folders ({error})") from error

    return existing


def _occurrences(finding: Finding) -> int:
    """How often the finding occurs on its page: one per redacted area, and at least one, since a detected string the search missed still occurred."""
    return max(1, len(finding.areas))


def _position(finding: Finding) -> tuple[float, float, float]:
    """Where the finding first occurs, for reading order: page, then top to bottom, then left to right."""
    first = min(finding.areas, key=lambda area: (area[1], area[0]), default=None)

    return (finding.page, first[1], first[0]) if first else (finding.page, math.inf, math.inf)


def _is_full_name(name: str) -> bool:
    return sum(word[:1].isupper() for word in name.split()) >= MIN_FULL_NAME_WORDS


def candidate_name(findings: list[Finding]) -> str | None:
    """The person a document (e.g. a CV) is most likely about: the PERSON full name, of at least two capitalized words, that occurs most often over all pages.
    Mentions of one of its words alone (the first name or the surname) count toward it. A tie goes to the name that appears first. None if there is no full name."""
    persons = [(" ".join(finding.text.split()), finding) for finding in findings if finding.entity_type == PERSON]
    full_names = {name for name, _ in persons if _is_full_name(name)}

    if not full_names:
        return None

    def count(full_name: str) -> int:
        return sum(_occurrences(finding) for name, finding in persons if name == full_name or (" " not in name and name in full_name.split()))

    def first_seen(full_name: str) -> tuple[float, float, float]:
        return min(_position(finding) for name, finding in persons if name == full_name)

    return min(full_names, key=lambda full_name: (-count(full_name), first_seen(full_name)))


def key_markdown(file_id: str, candidate: str, original: str, output: Path, processed_at: datetime, exit_code: int) -> str:
    """The key file for one input: it links the UUID to the candidate and the original file name. It holds personal data and must not be shared with processed/."""
    return "\n".join([
        f"# {file_id}",
        "",
        f"- **Candidate:** {candidate} *(detected automatically — check it)*",
        f"- **Original file:** {original}",
        f"- **Redacted file:** {PROCESSED_FOLDER}/{output.name}",
        f"- **Processed:** {processed_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- **Result:** {_RESULTS[exit_code]}",
        "",
    ])


def write_key(folder: Path, file_id: str, candidate: str, original: str, output: Path, processed_at: datetime, exit_code: int) -> None:
    (folder / KEYS_FOLDER / f"{file_id}.md").write_text(key_markdown(file_id, candidate, original, output, processed_at, exit_code), encoding="utf-8")
