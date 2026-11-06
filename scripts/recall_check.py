"""Developer tool: measure recall and precision of the detector on synthetic documents.

Run it with: python -m scripts.recall_check [--lang da,en] [--seed N] [--show-misses]

It builds ~10 documents with known PII (Faker da_DK and en_US), runs the detector, and prints recall and precision per
entity type. The Danish PERSON recall is the go/no-go for the spaCy vs DaCy decision (F04, SC-03). Only synthetic data is used.
"""
import argparse
import random

from faker import Faker

from pii_strip.detector import find_pii_results
from pii_strip.nlp import parse_languages

ENTITIES = ["PERSON", "LOCATION", "EMAIL_ADDRESS", "DK_PHONE", "DK_CPR"]


def score(documents: list[tuple[set[tuple[str, str]], set[tuple[str, str]]]]) -> dict[str, dict[str, float | None]]:
    """Recall and precision per entity type, summed over documents. Each document is a pair (expected, found) of sets of (entity type, string).
    An expected item is found if a finding of the same type contains it (so 'Kære Mette Hansen' still covers 'Mette Hansen' in the redaction).
    A finding is correct if it contains, or is contained in, an expected item of the same type."""
    totals: dict[str, dict[str, int]] = {}

    for expected, found in documents:
        for entity in {entity for entity, _ in expected} | {entity for entity, _ in found}:
            counts = totals.setdefault(entity, {"expected": 0, "found": 0, "recalled": 0, "correct": 0})
            expected_strings = [value for kind, value in expected if kind == entity]
            found_strings = [value for kind, value in found if kind == entity]

            counts["expected"] += len(expected_strings)
            counts["found"] += len(found_strings)
            counts["recalled"] += sum(1 for value in expected_strings if any(value in other for other in found_strings))
            counts["correct"] += sum(1 for value in found_strings if any(value in other or other in value for other in expected_strings))

    return {entity: {"recall": c["recalled"] / c["expected"] if c["expected"] else None, "precision": c["correct"] / c["found"] if c["found"] else None, "expected": c["expected"], "found": c["found"]} for entity, c in sorted(totals.items())}


class _Document:
    """Text built from fragments; each PII fragment is registered with its entity type."""

    def __init__(self):
        self.parts: list[str] = []
        self.expected: set[tuple[str, str]] = set()

    def text(self, value: str):
        self.parts.append(value)

    def pii(self, entity: str, value: str):
        self.parts.append(value)
        self.expected.add((entity, value))

    def render(self) -> str:
        return "".join(self.parts)


def _phone(rng: random.Random) -> str:
    digits = "".join(str(rng.randint(0, 9)) for _ in range(8))

    return f"+45 {digits[0:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]}"


def _cpr(rng: random.Random) -> str:
    return f"{rng.randint(1, 28):02d}{rng.randint(1, 12):02d}{rng.randint(50, 99)}-{rng.randint(1000, 9999)}"


def build_documents(seed: int) -> list[tuple[str, str, set[tuple[str, str]]]]:
    """Return (name, text, expected) for about 10 synthetic documents: 5 Danish and 5 English."""
    rng = random.Random(seed)
    danish, english = Faker("da_DK"), Faker("en_US")
    Faker.seed(seed)
    documents = []

    for number in range(5):
        doc = _Document()
        doc.text("Til: ")
        doc.pii("PERSON", danish.first_name() + " " + danish.last_name())
        doc.text("\nVedr.: Din ansøgning\n\nKære ")
        doc.pii("PERSON", danish.first_name() + " " + danish.last_name())
        doc.text(", tak for dit brev. Vi har talt med ")
        doc.pii("PERSON", danish.first_name() + " " + danish.last_name())
        doc.text(" fra Novo Nordisk om sagen. Du bor i ")
        doc.pii("LOCATION", danish.city())
        doc.text(". Ring på ")
        doc.pii("DK_PHONE", _phone(rng))
        doc.text(" eller skriv til ")
        doc.pii("EMAIL_ADDRESS", danish.email())
        doc.text(". CPR-nummer: ")
        doc.pii("DK_CPR", _cpr(rng))
        doc.text(".\n\nMed venlig hilsen\n")
        doc.pii("PERSON", danish.first_name() + " " + danish.last_name())
        documents.append((f"da-{number + 1}", doc.render(), doc.expected))

    for number in range(5):
        doc = _Document()
        doc.text("From: ")
        doc.pii("PERSON", english.first_name() + " " + english.last_name())
        doc.text("\nSubject: Your application\n\nDear ")
        doc.pii("PERSON", english.first_name() + " " + english.last_name())
        doc.text(", thank you for your letter. We spoke with ")
        doc.pii("PERSON", english.first_name() + " " + english.last_name())
        doc.text(" at Microsoft about the case. You live in ")
        doc.pii("LOCATION", english.city())
        doc.text(". Call ")
        doc.pii("DK_PHONE", _phone(rng))
        doc.text(" or write to ")
        doc.pii("EMAIL_ADDRESS", english.email())
        doc.text(".\n\nKind regards\n")
        doc.pii("PERSON", english.first_name() + " " + english.last_name())
        documents.append((f"en-{number + 1}", doc.render(), doc.expected))

    return documents


def run(languages: list[str], seed: int, show_misses: bool) -> None:
    results = []

    for name, text, expected in build_documents(seed):
        found = {(result.entity_type, text[result.start:result.end]) for result in find_pii_results(text, languages, ENTITIES)}
        results.append((name, expected, found))

        if show_misses:
            for entity, value in sorted(expected):
                if not any(kind == entity and value in other for kind, other in found):
                    print(f"  MISSED   {name} {entity}: {value}")

            for entity, value in sorted(found - expected):
                print(f"  EXTRA    {name} {entity}: {value}")

    for title, wanted in [("Danish documents", "da"), ("English documents", "en"), ("All documents", "")]:
        print(f"\n{title} (languages: {','.join(languages)})")
        print(f"{'entity':<15}{'recall':>8}{'precision':>11}{'expected':>10}{'found':>7}")

        for entity, metrics in score([(expected, found) for name, expected, found in results if name.startswith(wanted)]).items():
            recall = "n/a" if metrics["recall"] is None else f"{metrics['recall']:.2f}"
            precision = "n/a" if metrics["precision"] is None else f"{metrics['precision']:.2f}"
            print(f"{entity:<15}{recall:>8}{precision:>11}{metrics['expected']:>10}{metrics['found']:>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recall and precision of the PII detector on synthetic documents")
    parser.add_argument("--lang", help="languages to analyze with (default: da,en)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--show-misses", action="store_true", help="print every missed and extra finding")
    args = parser.parse_args()

    run(parse_languages(args.lang), args.seed, args.show_misses)


if __name__ == "__main__":
    main()
