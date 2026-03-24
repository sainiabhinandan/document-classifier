from django.urls import path

from .views import DocumentClassifyView, DocumentDetailView, DocumentListView

urlpatterns = [
    path("classify/", DocumentClassifyView.as_view(), name="document-classify"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("", DocumentListView.as_view(), name="document-list"),
]
