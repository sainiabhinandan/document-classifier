import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from django.conf import settings

from documents.models import ConfidenceLevel, DocumentCategory

from .llm import LLMServiceError, get_llm_service
from .text_extraction import TextExtractionError, extract_text

EXPECTED_FIELDS = {
    DocumentCategory.IDENTITY_DOCUMENT: [
        "first_name",
        "last_name",
        "date_of_birth",
        "document_number",
        "expiry_date",
    ],
    DocumentCategory.PAYSLIP: [
        "employee_name",
        "employer",
        "period",
        "gross_salary",
        "net_salary",
    ],
    DocumentCategory.INVOICE: [
        "issuer",
        "recipient",
        "invoice_number",
        "invoice_date",
        "total_amount",
    ],
}


class DocumentProcessingError(Exception):
    pass


def process_document(file_name: str, file_bytes: bytes) -> dict:
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_process_sync, file_name, file_bytes)
        try:
            result = future.result(timeout=settings.DOCUMENT_TIMEOUT_SECONDS)
        except FuturesTimeoutError as exc:
            raise DocumentProcessingError("Document processing timed out.") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result["processing_time_ms"] = elapsed_ms
    return result


def _process_sync(file_name: str, file_bytes: bytes) -> dict:
    try:
        raw_text = extract_text(file_name, file_bytes)
    except TextExtractionError as exc:
        raise DocumentProcessingError(str(exc)) from exc

    if not raw_text:
        raw_text = ""

    llm_service = get_llm_service()
    try:
        llm_result = llm_service.classify_and_extract(raw_text)
    except LLMServiceError as exc:
        raise DocumentProcessingError(str(exc)) from exc

    category = normalize_category(llm_result.category)
    extracted_fields = llm_result.extracted_fields or {}
    confidence = compute_confidence(category, extracted_fields, raw_text)

    return {
        "category": category,
        "extracted_fields": extracted_fields,
        "confidence": confidence,
        "raw_text": raw_text,
        "model_used": llm_result.model_used,
    }


def normalize_category(category: str) -> str:
    valid_categories = {value for value, _ in DocumentCategory.choices}
    if category in valid_categories:
        return category
    return DocumentCategory.OTHER


def compute_confidence(category: str, extracted_fields: dict, raw_text: str) -> str:
    expected = EXPECTED_FIELDS.get(category, [])
    text_len = len(raw_text.strip())

    if not expected:
        if text_len >= 160:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    present = 0
    for field in expected:
        value = extracted_fields.get(field)
        if value is not None and str(value).strip() != "":
            present += 1

    completeness = present / len(expected)

    if completeness >= 0.75 and text_len >= 120:
        return ConfidenceLevel.HIGH
    if completeness >= 0.4 and text_len >= 40:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
