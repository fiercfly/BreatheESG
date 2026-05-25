from django.urls import path
from .views import IngestView, MetricsView, RecordListView, RecordDetailView, BulkApproveView, BulkLockView, AuditTrailView

urlpatterns = [
    path('ingest/', IngestView.as_view(), name='api_ingest'),
    path('metrics/', MetricsView.as_view(), name='api_metrics'),
    path('records/', RecordListView.as_view(), name='api_records'),
    path('records/<int:pk>/', RecordDetailView.as_view(), name='api_record_detail'),
    path('records/bulk-approve/', BulkApproveView.as_view(), name='api_bulk_approve'),
    path('records/bulk-lock/', BulkLockView.as_view(), name='api_bulk_lock'),
    path('audit-trail/', AuditTrailView.as_view(), name='api_audit_trail'),
]
