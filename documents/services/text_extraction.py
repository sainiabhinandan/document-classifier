import io

import pdfplumber
import pytesseract
from PIL import Image


class TextExtractionError(Exception):
    pass


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def extract_text(file_name: str, file_bytes: bytes) -> str:
    lower_name = file_name.lower()
    if lower_name.endswith(".pdf"):
        return _extract_pdf_text(file_bytes)
    if lower_name.endswith((".jpg", ".jpeg", ".png")):
        return _extract_image_text(file_bytes)
    raise TextExtractionError("Unsupported file format.")


def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        pages_text: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
        return "\n".join(pages_text).strip()
    except Exception as exc:
        raise TextExtractionError("Failed to extract text from PDF.") from exc


def _extract_image_text(file_bytes: bytes) -> str:
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            return pytesseract.image_to_string(image).strip()
    except Exception as exc:
        raise TextExtractionError("Failed to extract text from image.") from exc
