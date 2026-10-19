import pymupdf
import pytest

from finpulse.parse import OcrUnavailable, parse_file, parse_html, parse_pdf
from finpulse.parse.ocr import ocr_png

BODY = (
    "The Adjudicating Officer imposed a penalty of Rs. 25,00,000 on Yes Bank Limited "
    "under Section 15HA of the SEBI Act for violation of the PFUTP Regulations."
)


def _text_pdf(path, pages=2):
    doc = pymupdf.open()
    for n in range(pages):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 400), f"{BODY} Page body {n + 1}.", fontsize=12)
    doc.save(path)
    doc.close()


def _scanned_pdf(path):
    """A PDF whose only content is a picture of text, like a scanned order."""
    src = pymupdf.open()
    page = src.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 540, 400), BODY, fontsize=14)
    pix = page.get_pixmap(dpi=200)
    out = pymupdf.open()
    img_page = out.new_page(width=page.rect.width, height=page.rect.height)
    img_page.insert_image(img_page.rect, stream=pix.tobytes("png"))
    out.save(path)
    out.close()
    src.close()


def test_text_layer_is_read_without_ocr(tmp_path):
    pdf = tmp_path / "text.pdf"
    _text_pdf(pdf)
    parsed = parse_pdf(pdf, min_words_per_page=5)
    assert len(parsed.pages) == 2
    assert not parsed.ocr_used
    assert "Yes Bank Limited" in parsed.pages[0].text


def test_scanned_page_goes_through_ocr(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    parsed = parse_pdf(pdf, min_words_per_page=5)
    assert parsed.ocr_used
    text = " ".join(parsed.pages[0].text.split())  # OCR keeps the scan's line breaks
    assert "Adjudicating Officer" in text
    assert "Yes Bank Limited" in text
    assert "15HA" in text


def test_ocr_can_be_switched_off(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    parsed = parse_pdf(pdf, ocr=False)
    assert not parsed.ocr_used
    assert parsed.pages[0].text == ""


def test_missing_tesseract_is_an_error_not_empty_text(tmp_path, monkeypatch):
    monkeypatch.setattr("finpulse.parse.ocr.shutil.which", lambda _: None)
    with pytest.raises(OcrUnavailable):
        ocr_png(b"not a png")


def test_html_main_content():
    html = (
        "<html><body><nav>Menu Home About</nav><article><h1>Order</h1>"
        f"<p>{BODY}</p><p>The order is effective immediately.</p></article>"
        "<footer>Copyright</footer></body></html>"
    )
    text = parse_html(html).pages[0].text
    assert "Yes Bank Limited" in text
    assert "effective immediately" in text


def test_dispatch_by_extension(tmp_path):
    txt = tmp_path / "order.txt"
    txt.write_text("Plain text order.")
    assert parse_file(txt).pages[0].text == "Plain text order."
    with pytest.raises(ValueError):
        parse_file(tmp_path / "order.docx")


def test_paragraphs_are_rebuilt_from_line_spacing(tmp_path):
    pdf = tmp_path / "paras.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    # one block per line, as many regulatory PDFs are produced
    for para in (
        ["The Board met on Monday and", "approved the proposal after a", "lengthy discussion."],
        ["The second paragraph starts", "here and also wraps."],
    ):
        for line in para:
            page.insert_text((72, y), line, fontsize=11)
            y += 14
        y += 12
    doc.save(pdf)
    doc.close()
    text = parse_pdf(pdf, ocr=False).pages[0].text
    first, second = text.split("\n\n")
    assert first.split("\n") == [
        "The Board met on Monday and",
        "approved the proposal after a",
        "lengthy discussion.",
    ]
    assert second.split("\n") == ["The second paragraph starts", "here and also wraps."]
