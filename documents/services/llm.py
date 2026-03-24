import json
from dataclasses import dataclass

import requests
from anthropic import Anthropic
from django.conf import settings
from openai import OpenAI


class LLMServiceError(Exception):
    pass


@dataclass
class LLMResult:
    category: str
    extracted_fields: dict
    model_used: str


class BaseLLMService:
    def classify_and_extract(self, text: str) -> LLMResult:
        raise NotImplementedError


class RemoteLLMService(BaseLLMService):
    def classify_and_extract(self, text: str) -> LLMResult:
        prompt = build_prompt(text)
        backend = settings.REMOTE_LLM_BACKEND

        if backend == "openai":
            if not settings.OPENAI_API_KEY:
                raise LLMServiceError("OPENAI_API_KEY is not configured.")
            client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.DOCUMENT_TIMEOUT_SECONDS)
            response = client.responses.create(
                model=settings.REMOTE_MODEL,
                input=prompt,
                max_output_tokens=700,
            )
            content = response.output_text
        elif backend == "groq":
            if not settings.GROQ_API_KEY:
                raise LLMServiceError("GROQ_API_KEY is not configured.")
            client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                timeout=settings.DOCUMENT_TIMEOUT_SECONDS,
            )
            response = client.chat.completions.create(
                model=settings.REMOTE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
        elif backend == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise LLMServiceError("ANTHROPIC_API_KEY is not configured.")
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.DOCUMENT_TIMEOUT_SECONDS)
            response = client.messages.create(
                model=settings.REMOTE_MODEL,
                max_tokens=700,
                messages=[{"role": "user", "content": prompt}],
            )
            content = "".join(block.text for block in response.content if hasattr(block, "text"))
        else:
            raise LLMServiceError("Unsupported REMOTE_LLM_BACKEND.")

        payload = parse_llm_json(content)
        return LLMResult(
            category=payload.get("category", "other"),
            extracted_fields=payload.get("extracted_fields", {}) or {},
            model_used=settings.REMOTE_MODEL,
        )


class LocalLLMService(BaseLLMService):
    def classify_and_extract(self, text: str) -> LLMResult:
        payload = {
            "model": settings.LOCAL_MODEL,
            "prompt": build_prompt(text),
            "stream": False,
            "options": {"num_predict": 700},
        }

        try:
            response = requests.post(
                settings.OLLAMA_URL,
                json=payload,
                timeout=settings.DOCUMENT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except Exception as exc:
            raise LLMServiceError("Local LLM service is unavailable.") from exc

        content = response.json().get("response", "")
        parsed = parse_llm_json(content)
        return LLMResult(
            category=parsed.get("category", "other"),
            extracted_fields=parsed.get("extracted_fields", {}) or {},
            model_used=settings.LOCAL_MODEL,
        )


def build_prompt(text: str) -> str:
    trimmed_text = text[:12000]
    return (
        "You are a document classification system. "
        "Classify the document into one category from: "
        "identity_document, employment_contract, payslip, invoice, tax_form, other. "
        "Then extract key fields as JSON. "
        "Return only valid JSON with this exact structure: "
        '{"category":"...","extracted_fields":{...}}. '
        "Use these category hints and fields:\n"
        "identity_document: first_name, last_name, date_of_birth, document_number, expiry_date\n"
        "payslip: employee_name, employer, period, gross_salary, net_salary\n"
        "invoice: issuer, recipient, invoice_number, invoice_date, total_amount\n"
        "employment_contract: employee_name, employer, start_date, contract_type\n"
        "tax_form: taxpayer_name, tax_code, tax_year, issuing_authority\n"
        f"Document text:\n{trimmed_text}"
    )


def parse_llm_json(content: str) -> dict:
    if not content:
        raise LLMServiceError("Empty response from LLM.")

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMServiceError("LLM did not return valid JSON.")

    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMServiceError("Failed to parse LLM JSON output.") from exc


def get_llm_service() -> BaseLLMService:
    provider = settings.LLM_PROVIDER
    if provider == "local":
        return LocalLLMService()
    if provider == "remote":
        return RemoteLLMService()
    raise LLMServiceError("Unsupported LLM_PROVIDER. Use local or remote.")
