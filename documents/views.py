from django.conf import settings
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DocumentRecord
from .serializers import DocumentDetailSerializer, DocumentListSerializer
from .services.pipeline import DocumentProcessingError, process_document

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class DocumentClassifyView(APIView):
	parser_classes = [MultiPartParser, FormParser]

	def post(self, request, *args, **kwargs):
		files = request.FILES.getlist("files")

		if not files:
			return Response({"detail": "No files uploaded."}, status=status.HTTP_400_BAD_REQUEST)

		if len(files) > settings.MAX_FILES_PER_REQUEST:
			return Response(
				{"detail": f"Maximum {settings.MAX_FILES_PER_REQUEST} files per request."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
		records: list[DocumentRecord] = []

		for uploaded in files:
			name = uploaded.name or ""
			lower_name = name.lower()

			if not any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
				return Response(
					{"detail": f"Invalid file format for '{name}'. Allowed: PDF, JPEG, PNG."},
					status=status.HTTP_400_BAD_REQUEST,
				)

			if uploaded.size > max_size:
				return Response(
					{"detail": f"File '{name}' exceeds size limit of {settings.MAX_UPLOAD_SIZE_MB} MB."},
					status=status.HTTP_400_BAD_REQUEST,
				)

			try:
				result = process_document(name, uploaded.read())
			except DocumentProcessingError as exc:
				message = str(exc)
				error_status = (
					status.HTTP_503_SERVICE_UNAVAILABLE
					if "llm" in message.lower() or "api_key" in message.lower() or "unavailable" in message.lower()
					else status.HTTP_400_BAD_REQUEST
				)
				if "timed out" in message.lower():
					error_status = status.HTTP_504_GATEWAY_TIMEOUT
				return Response({"detail": message}, status=error_status)

			record = DocumentRecord.objects.create(
				filename=name,
				category=result["category"],
				confidence=result["confidence"],
				extracted_fields=result["extracted_fields"],
				raw_text=result["raw_text"],
				model_used=result["model_used"],
				processing_time_ms=result["processing_time_ms"],
			)
			records.append(record)

		data = DocumentDetailSerializer(records, many=True).data
		return Response({"results": data}, status=status.HTTP_201_CREATED)


class DocumentDetailView(generics.RetrieveAPIView):
	queryset = DocumentRecord.objects.all()
	serializer_class = DocumentDetailSerializer


class DocumentListView(generics.ListAPIView):
	queryset = DocumentRecord.objects.all()
	serializer_class = DocumentListSerializer
	filterset_fields = ["category", "confidence"]
