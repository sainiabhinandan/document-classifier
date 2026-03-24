# Document Classifier MVP (Django + DRF)

Basic working prototype for classifying uploaded documents and extracting key fields with an LLM.

## Stack
- Python 3.10+
- Django 4+
- Django REST Framework
- SQLite

## Why these extraction libraries
- **PDF: `pdfplumber`** — simple API, reliable plain-text extraction from many business PDFs, fast to integrate in an MVP.
- **OCR: `pytesseract`** — widely used OCR wrapper, easy setup, good enough for prototype-level extraction.

## Endpoints
- `POST /api/documents/classify/`
  - multipart upload, key `files`
  - max 3 files per request
  - allowed: PDF/JPEG/PNG
  - max size: 5 MB each
- `GET /api/documents/{id}/`
- `GET /api/documents/?category=payslip&confidence=high`

## Categories
- `identity_document`
- `employment_contract`
- `payslip`
- `invoice`
- `tax_form`
- `other`

## Extracted fields (minimum defined for 3 categories)
- `identity_document`: `first_name`, `last_name`, `date_of_birth`, `document_number`, `expiry_date`
- `payslip`: `employee_name`, `employer`, `period`, `gross_salary`, `net_salary`
- `invoice`: `issuer`, `recipient`, `invoice_number`, `invoice_date`, `total_amount`

## Confidence heuristic
Confidence is computed from:
1. **Completeness** = extracted non-empty fields / expected fields (for known category schemas)
2. **Text length** of extracted text

Rules:
- `high`: completeness >= 0.75 and text length >= 120
- `medium`: completeness >= 0.40 and text length >= 40
- otherwise `low`
- for categories without explicit schema, confidence depends only on text length (`medium` if >= 160, else `low`)

## LLM modes (common interface)
Configured with environment variables.

- `LLM_PROVIDER=remote`
  - `REMOTE_LLM_BACKEND=openai|anthropic|groq`
  - `REMOTE_MODEL=...`
  - API key in `.env` only
- `LLM_PROVIDER=local`
  - Uses Ollama endpoint (`OLLAMA_URL`) and `LOCAL_MODEL`

## Setup (no Docker)
1. Create venv and install deps:
   - `pip install -r requirements.txt`
2. Copy env:
   - `copy .env.example .env` (Windows)
3. Run migrations:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
4. Start server:
   - `python manage.py runserver`

### Quick setup with Groq
Set in `.env`:
- `LLM_PROVIDER=remote`
- `REMOTE_LLM_BACKEND=groq`
- `REMOTE_MODEL=llama-3.3-70b-versatile` (or another Groq model)
- `GROQ_API_KEY=your_key_here`

## Notes for OCR
`pytesseract` requires Tesseract OCR installed on your machine and available in `PATH`.

## Example curl
```bash
curl -X POST http://127.0.0.1:8000/api/documents/classify/ \
  -F "files=@sample.pdf"
```

## Testing
Run:
- `pytest`

Covered cases:
- single and multiple happy path
- invalid file
- file too large
- unreachable LLM (mock)
- retrieval existing result
- non-existent ID
- filter by category/confidence

## AI Usage
This project was developed with AI assistance.

- Tools used: GitHub Copilot / LLM assistance for scaffolding, endpoint structure, and test drafting.
- Example prompt iteration:
  - Initial: "Create Django endpoint for multipart files and classify with LLM"
  - Refined: "Keep MVP only, max 3 files, 5MB validation, return category/confidence/raw text preview"
- Correction example:
  - AI initially suggested returning full raw text. This was adjusted to a preview field to keep responses lighter and safer.
