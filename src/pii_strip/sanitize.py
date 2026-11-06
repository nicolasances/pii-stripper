from dataclasses import dataclass

import pymupdf

METADATA_FIELDS = ("title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate")


@dataclass
class SanitizeCounts:
    """How much hidden content was removed. Passed to the report (F09)."""

    metadata_fields: int = 0
    xmp: int = 0
    annotations: int = 0
    form_fields: int = 0
    embedded_files: int = 0
    bookmarks: int = 0


def _remove_form_fields(doc: pymupdf.Document) -> int:
    removed = 0

    for page in doc:
        for widget in list(page.widgets()):
            page.delete_widget(widget)
            removed += 1

    catalog = doc.pdf_catalog()

    if doc.xref_get_key(catalog, "AcroForm")[0] != "null":
        doc.xref_set_key(catalog, "AcroForm", "null")

    return removed


def _remove_annotations(doc: pymupdf.Document) -> int:
    removed = 0

    for page in doc:
        for annot in list(page.annots()):
            page.delete_annot(annot)
            removed += 1

    return removed


def _remove_embedded_files(doc: pymupdf.Document) -> int:
    names = list(doc.embfile_names())

    for name in names:
        doc.embfile_del(name)

    return len(names)


def _remove_bookmarks(doc: pymupdf.Document) -> int:
    removed = len(doc.get_toc())
    doc.set_toc([])

    return removed


def _clear_metadata(doc: pymupdf.Document) -> int:
    cleared = sum(1 for field in METADATA_FIELDS if doc.metadata.get(field))
    doc.set_metadata({})

    return cleared


def _remove_xmp(doc: pymupdf.Document) -> int:
    had_xmp = bool(doc.get_xml_metadata().strip())
    doc.del_xml_metadata()

    return 1 if had_xmp else 0


def sanitize(doc: pymupdf.Document, keep_outline: bool = False) -> SanitizeCounts:
    """Remove the hidden content from the document, in place: metadata, XMP, annotations, form fields, embedded files and, unless kept, bookmarks."""
    counts = SanitizeCounts()
    counts.form_fields = _remove_form_fields(doc)
    counts.annotations = _remove_annotations(doc)
    counts.embedded_files = _remove_embedded_files(doc)
    counts.bookmarks = 0 if keep_outline else _remove_bookmarks(doc)
    counts.metadata_fields = _clear_metadata(doc)
    counts.xmp = _remove_xmp(doc)

    return counts
