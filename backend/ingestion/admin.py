from django.contrib import admin
from .models import Organization, UserProfile, IngestionJob, RawRecord, NormalizedRecord, AuditTrail

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization')

@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_type', 'status', 'file_name', 'created_at')
    list_filter = ('source_type', 'status')

@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'ingestion_job', 'created_at')

@admin.register(NormalizedRecord)
class NormalizedRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'source_type', 'scope', 'category', 'co2e_kg', 'status', 'suspicious_flag')
    list_filter = ('source_type', 'scope', 'status', 'suspicious_flag')

@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ('id', 'normalized_record', 'user', 'action', 'timestamp')
    list_filter = ('action',)
