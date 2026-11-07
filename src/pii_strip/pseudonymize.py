import shutil
from datetime import datetime
from pathlib import Path

PROCESSED_FOLDER = "processed"
KEYS_FOLDER = "keys"
UNKNOWN_CANDIDATE = "unknown"
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
