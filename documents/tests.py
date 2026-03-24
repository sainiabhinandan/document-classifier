from unittest.mock import patch

from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ConfidenceLevel, DocumentCategory, DocumentRecord
from .services.pipeline import DocumentProcessingError


class DocumentApiTests(APITestCase):
	def _upload(self, name: str, size: int = 100, content_type: str = "application/octet-stream"):
		upload = SimpleUploadedFile(name=name, content=b"x" * size, content_type=content_type)
		return {"files": [upload]}

	@patch("documents.views.process_document")
	def test_classify_single_file_happy_path(self, mocked_process):
		mocked_process.return_value = {
			"category": DocumentCategory.PAYSLIP,
			"extracted_fields": {"employee_name": "Mario Rossi"},
			"confidence": ConfidenceLevel.HIGH,
			"raw_text": "Payslip text",
			"model_used": "test-model",
			"processing_time_ms": 10,
		}

		response = self.client.post(
			reverse("document-classify"),
			data=self._upload("payslip.png", content_type="image/png"),
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(len(response.data["results"]), 1)
		self.assertEqual(DocumentRecord.objects.count(), 1)

	@patch("documents.views.process_document")
	def test_classify_multiple_files_happy_path(self, mocked_process):
		mocked_process.return_value = {
			"category": DocumentCategory.INVOICE,
			"extracted_fields": {"invoice_number": "INV-1"},
			"confidence": ConfidenceLevel.MEDIUM,
			"raw_text": "Invoice text",
			"model_used": "test-model",
			"processing_time_ms": 12,
		}

		response = self.client.post(
			reverse("document-classify"),
			data={
				"files": [
					SimpleUploadedFile("inv1.pdf", b"a", content_type="application/pdf"),
					SimpleUploadedFile("inv2.png", b"b", content_type="image/png"),
				]
			},
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(len(response.data["results"]), 2)

	def test_invalid_file_extension(self):
		response = self.client.post(
			reverse("document-classify"),
			data=self._upload("notes.txt"),
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_file_too_large(self):
		huge_size = 5 * 1024 * 1024 + 1
		response = self.client.post(
			reverse("document-classify"),
			data=self._upload("large.pdf", size=huge_size, content_type="application/pdf"),
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	@patch("documents.views.process_document")
	def test_unreachable_llm(self, mocked_process):
		mocked_process.side_effect = DocumentProcessingError("LLM service unavailable")
		response = self.client.post(
			reverse("document-classify"),
			data=self._upload("doc.pdf", content_type="application/pdf"),
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

	def test_get_existing_document(self):
		record = DocumentRecord.objects.create(
			filename="doc.pdf",
			category=DocumentCategory.PAYSLIP,
			confidence=ConfidenceLevel.HIGH,
			extracted_fields={"employee_name": "Alice"},
			raw_text="sample",
			model_used="test",
			processing_time_ms=11,
		)

		response = self.client.get(reverse("document-detail", kwargs={"pk": str(record.id)}))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(str(response.data["id"]), str(record.id))

	def test_get_non_existent_document(self):
		response = self.client.get(reverse("document-detail", kwargs={"pk": "25f98a57-a17f-4196-b2a7-68f61dbec798"}))
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_filter_by_category_and_confidence(self):
		DocumentRecord.objects.create(
			filename="payslip.pdf",
			category=DocumentCategory.PAYSLIP,
			confidence=ConfidenceLevel.HIGH,
			extracted_fields={},
			raw_text="a",
			model_used="m",
			processing_time_ms=1,
		)
		DocumentRecord.objects.create(
			filename="invoice.pdf",
			category=DocumentCategory.INVOICE,
			confidence=ConfidenceLevel.LOW,
			extracted_fields={},
			raw_text="b",
			model_used="m",
			processing_time_ms=1,
		)

		response = self.client.get(reverse("document-list"), {"category": "payslip", "confidence": "high"})
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data["results"]), 1)
