import math
from pathlib import Path

DEFAULT_THRESHOLD = 0.5


def read_term_list(path: Path) -> list[str]:
    """Read a deny or allow list: UTF-8, one term per line. Blank lines and lines starting with '#' are ignored, and whitespace around a term is trimmed."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read the term list {path} ({error})") from error

    terms = [line.strip() for line in lines]

    return [term for term in terms if term and not term.startswith("#")]


def parse_threshold(value: str | None) -> float:
    if value is None:
        return DEFAULT_THRESHOLD

    try:
        threshold = float(value)
    except ValueError:
        raise ValueError(f"invalid threshold {value!r}: it must be a number from 0 to 1") from None

    if math.isnan(threshold) or not 0 <= threshold <= 1:
        raise ValueError(f"invalid threshold {value!r}: it must be a number from 0 to 1")

    return threshold
