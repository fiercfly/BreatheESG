from django.db import models
from django.contrib.auth.models import User

class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users')

    def __str__(self):
        return f"{self.user.username} ({self.organization.name})"

class IngestionJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ingestion_jobs')
    source_type = models.CharField(max_length=50)  # SAP, UTILITY, TRAVEL
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file_name = models.CharField(max_length=255)
    error_logs = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} - {self.status} ({self.file_name})"

class RawRecord(models.Model):
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='raw_records')
    raw_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RawRecord for Job {self.ingestion_job.id}"

class NormalizedRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('LOCKED_FOR_AUDIT', 'Locked For Audit'),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='normalized_records')
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name='normalized_record', null=True, blank=True)
    source_type = models.CharField(max_length=50)  # SAP, UTILITY, TRAVEL
    scope = models.CharField(max_length=10)  # Scope 1, Scope 2, Scope 3
    category = models.CharField(max_length=100)  # e.g., Stationary Combustion, Purchased Electricity, Flights, Hotels
    raw_quantity = models.DecimalField(max_digits=20, decimal_places=4)
    raw_unit = models.CharField(max_length=50)
    normalized_quantity = models.DecimalField(max_digits=20, decimal_places=4)
    normalized_unit = models.CharField(max_length=50)
    co2e_kg = models.DecimalField(max_digits=20, decimal_places=4)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    suspicious_flag = models.BooleanField(default=False)
    suspicious_reason = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_records')
    approved_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.source_type} - {self.category} - {self.co2e_kg} kg CO2e"

class AuditTrail(models.Model):
    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name='audit_trails')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions')
    action = models.CharField(max_length=100)  # e.g. UPLOADED, EDITED, APPROVED, LOCKED, UNLOCKED
    changes = models.JSONField(default=dict)  # e.g. {"co2e_kg": {"old": "100.00", "new": "120.00"}}
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on Record {self.normalized_record.id} by {self.user.username if self.user else 'System'}"
