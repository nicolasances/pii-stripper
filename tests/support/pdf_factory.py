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


HIDDEN_PII = {
    "author": "Hidden Author Hansen",
    "xmp": "xmp.creator.hansen@example.invalid",
    "comment": "Reviewer Rikke Reviewer says check this",
    "form_value": "Formvalue Fridolin Fjeldsted",
    "attachment": "Attachment Agnete Andersen",
    "bookmark": "Bookmark Bent Bertelsen",
}


def make_hidden_pii_pdf(path: Path) -> Path:
    """Create a PDF with synthetic PII in metadata, XMP, a comment, a form field, an attachment and a bookmark. The visible text holds no PII."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Quarterly report for the board", fontsize=11)
    doc.set_metadata({"author": HIDDEN_PII["author"], "title": "Report", "subject": "Board", "keywords": "board", "creator": "Writer", "producer": "Writer"})
    doc.set_xml_metadata(f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description><creator>{HIDDEN_PII["xmp"]}</creator></rdf:Description></rdf:RDF></x:xmpmeta>')
    page.add_text_annot((300, 72), HIDDEN_PII["comment"])
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "full_name"
    widget.field_value = HIDDEN_PII["form_value"]
    widget.rect = pymupdf.Rect(72, 120, 300, 140)
    page.add_widget(widget)
    doc.embfile_add("notes.txt", HIDDEN_PII["attachment"].encode())
    doc.set_toc([[1, HIDDEN_PII["bookmark"], 1]])
    doc.save(path)
    doc.close()

    return path


def raw_bytes_contain(path: Path, text: str) -> bool:
    return text.encode() in path.read_bytes()
