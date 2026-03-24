from django.conf import settings
from rest_framework import serializers

from .models import DocumentRecord


class DocumentDetailSerializer(serializers.ModelSerializer):
    raw_text_preview = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRecord
        fields = [
            "id",
            "filename",
            "category",
            "confidence",
            "extracted_fields",
            "raw_text_preview",
            "model_used",
            "processing_time_ms",
            "created_at",
        ]

    def get_raw_text_preview(self, obj: DocumentRecord) -> str:
        limit = settings.RAW_TEXT_PREVIEW_LENGTH
        return (obj.raw_text or "")[:limit]


class DocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRecord
        fields = ["id", "filename", "category", "confidence", "created_at"]
