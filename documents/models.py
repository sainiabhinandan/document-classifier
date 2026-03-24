from django.db import models
import uuid


class DocumentCategory(models.TextChoices):
	IDENTITY_DOCUMENT = "identity_document", "identity_document"
	EMPLOYMENT_CONTRACT = "employment_contract", "employment_contract"
	PAYSLIP = "payslip", "payslip"
	INVOICE = "invoice", "invoice"
	TAX_FORM = "tax_form", "tax_form"
	OTHER = "other", "other"


class ConfidenceLevel(models.TextChoices):
	HIGH = "high", "high"
	MEDIUM = "medium", "medium"
	LOW = "low", "low"


class DocumentRecord(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	filename = models.CharField(max_length=255)
	category = models.CharField(max_length=40, choices=DocumentCategory.choices)
	confidence = models.CharField(max_length=10, choices=ConfidenceLevel.choices)
	extracted_fields = models.JSONField(default=dict)
	raw_text = models.TextField(blank=True)
	model_used = models.CharField(max_length=100)
	processing_time_ms = models.PositiveIntegerField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.filename} ({self.category})"
