from pathlib import Path

import pymupdf


def make_pdf(path: Path, pages: list[str]) -> Path:
    """Create a text PDF with one page per string. Only ever pass synthetic (fake) PII."""
    doc = pymupdf.open()

    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)

    doc.save(path)
    doc.close()

    return path


def extract_text(path: Path) -> str:
    doc = pymupdf.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    return text


def page_count(path: Path) -> int:
    doc = pymupdf.open(path)
    count = doc.page_count
    doc.close()

    return count


def make_encrypted_pdf(path: Path, text: str) -> Path:
    """Create a password-protected PDF (synthetic content only)."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner-secret", user_pw="user-secret")
    doc.close()

    return path
