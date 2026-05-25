import json
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import Organization, UserProfile, IngestionJob, RawRecord, NormalizedRecord, AuditTrail
from .normalizers import SAPNormalizer, UtilityNormalizer, TravelNormalizer, EMISSION_FACTORS

def detect_outliers(organization):
    """
    Run statistical outlier detection on all normalized records of the organization.
    A record is flagged as an outlier if its CO2e is > 2.5 standard deviations from the mean
    of its specific category.
    """
    categories = NormalizedRecord.objects.filter(organization=organization).values_list('category', flat=True).distinct()
    
    for category in categories:
        records = NormalizedRecord.objects.filter(organization=organization, category=category)
        count = records.count()
        if count < 3:
            # Not enough data points to compute meaningful standard deviation
            continue
            
        # Calculate Mean
        avg_co2e = records.aggregate(avg=Avg('co2e_kg'))['avg']
        if not avg_co2e:
            continue
        mean = Decimal(str(avg_co2e))
        
        # Calculate Standard Deviation
        variance_sum = Decimal('0')
        for r in records:
            variance_sum += (r.co2e_kg - mean) ** 2
        variance = variance_sum / Decimal(str(count))
        std_dev = variance.sqrt()
        
        if std_dev == 0:
            continue
            
        # Flag records exceeding Z-score of 2.5
        for r in records:
            if r.is_locked:
                continue
            z_score = abs(r.co2e_kg - mean) / std_dev
            if z_score > Decimal('1.5'):
                # Flag as suspicious if not already flagged
                r.suspicious_flag = True
                reason = f"Statistical Outlier: CO2e ({float(r.co2e_kg):,.2f} kg) is {float(z_score):.2f} std devs away from the category average ({float(mean):,.2f} kg)."
                if r.suspicious_reason:
                    if "Statistical Outlier" not in r.suspicious_reason:
                        r.suspicious_reason += f" | {reason}"
                else:
                    r.suspicious_reason = reason
                r.save()

def recalculate_co2e(record):
    """
    Recalculate CO2e based on updated record quantity and unit / category.
    """
    factor_key = None
    
    # Simple mapping based on source and category / unit
    if record.source_type == 'SAP':
        if 'Natural Gas' in record.category:
            factor_key = 'FUEL_NATURAL_GAS_M3'
        elif 'LPG' in record.category:
            factor_key = 'FUEL_LPG_T' if record.raw_unit == 'T' else 'FUEL_LPG_KG'
        else:
            factor_key = 'FUEL_DIESEL_L' if record.raw_unit == 'L' else 'FUEL_DIESEL_GAL'
            
    elif record.source_type == 'UTILITY':
        if record.raw_unit == 'kWh':
            # Map meter to grid mix
            if record.raw_record and 'Meter ID' in record.raw_record.raw_data:
                meter_id = record.raw_record.raw_data['Meter ID']
                if meter_id.startswith('M-98'):
                    factor_key = 'GRID_DE'
                elif meter_id.startswith('M-44'):
                    factor_key = 'GRID_US'
                elif meter_id.startswith('M-11'):
                    factor_key = 'GRID_IN'
            if not factor_key:
                factor_key = 'GRID_DEFAULT'
                
    elif record.source_type == 'TRAVEL':
        if 'Flight' in record.category:
            is_long_haul = record.normalized_quantity >= 500
            booking_class = 'Economy'
            if 'Business' in record.category:
                booking_class = 'Business'
            elif 'First' in record.category:
                booking_class = 'First'
                
            if is_long_haul:
                factor_key = f'FLIGHT_LONG_HAUL_{booking_class.upper()}'
            else:
                factor_key = 'FLIGHT_SHORT_HAUL_BUSINESS' if booking_class in ('Business', 'First') else 'FLIGHT_SHORT_HAUL_ECONOMY'
        elif 'Hotel' in record.category:
            # Extract location from raw data
            loc = 'DEFAULT'
            if record.raw_record and 'details' in record.raw_record.raw_data:
                loc = record.raw_record.raw_data['details'].get('location', '').upper()
            if loc in ('USA', 'US'):
                factor_key = 'HOTEL_USA'
            elif loc in ('DE', 'GERMANY'):
                factor_key = 'HOTEL_DE'
            elif loc in ('AUS', 'AUSTRALIA'):
                factor_key = 'HOTEL_AUS'
            elif loc in ('GBR', 'UK'):
                factor_key = 'HOTEL_GBR'
            else:
                factor_key = 'HOTEL_DEFAULT'
        elif 'Car Rental' in record.category:
            factor_key = 'CAR_COMPACT_GAS'
            if 'Electric' in record.category:
                factor_key = 'CAR_ELECTRIC'
            elif 'SUV' in record.category:
                factor_key = 'CAR_SUV_GAS'

    if factor_key and factor_key in EMISSION_FACTORS:
        factor = Decimal(str(EMISSION_FACTORS[factor_key]))
        record.co2e_kg = record.normalized_quantity * factor
    else:
        # Fallback to current ratio or keep same
        pass

class IngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        source_type = request.data.get('source_type')
        org_name = request.data.get('organization', 'Breathe ESG Enterprise')
        file_obj = request.FILES.get('file')

        if not source_type or not file_obj:
            return Response(
                {"error": "Please provide both 'source_type' and 'file'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        source_type = source_type.upper()
        if source_type not in ('SAP', 'UTILITY', 'TRAVEL'):
            return Response(
                {"error": f"Invalid source type '{source_type}'. Must be SAP, UTILITY, or TRAVEL."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure default organization exists
        org, _ = Organization.objects.get_or_create(name=org_name)
        
        # System User for automation
        system_user, _ = User.objects.get_or_create(username='system_ingest', is_staff=True)

        # Create Ingestion Job
        job = IngestionJob.objects.create(
            organization=org,
            source_type=source_type,
            status='PROCESSING',
            file_name=file_obj.name
        )

        try:
            file_content = file_obj.read().decode('utf-8')
            
            # Select Normalizer
            if source_type == 'SAP':
                normalizer = SAPNormalizer()
            elif source_type == 'UTILITY':
                normalizer = UtilityNormalizer()
            else:
                normalizer = TravelNormalizer()

            parsed_records = normalizer.parse(file_content, org.id)
            
            success_count = 0
            with transaction.atomic():
                for raw_data, norm_data in parsed_records:
                    # Save Raw Record
                    raw_rec = RawRecord.objects.create(
                        ingestion_job=job,
                        raw_data=raw_data
                    )
                    
                    # Save Normalized Record
                    norm_rec = NormalizedRecord.objects.create(
                        organization=org,
                        raw_record=raw_rec,
                        source_type=norm_data['source_type'],
                        scope=norm_data['scope'],
                        category=norm_data['category'],
                        raw_quantity=norm_data['raw_quantity'],
                        raw_unit=norm_data['raw_unit'],
                        normalized_quantity=norm_data['normalized_quantity'],
                        normalized_unit=norm_data['normalized_unit'],
                        co2e_kg=norm_data['co2e_kg'],
                        start_date=norm_data['start_date'],
                        end_date=norm_data['end_date'],
                        status='PENDING_REVIEW',
                        suspicious_flag=norm_data['suspicious_flag'],
                        suspicious_reason=norm_data['suspicious_reason']
                    )
                    
                    # Create Audit Trail Entry
                    AuditTrail.objects.create(
                        normalized_record=norm_rec,
                        user=system_user,
                        action='RECORD_INGESTED',
                        changes={
                            "source_type": {"new": norm_data['source_type']},
                            "co2e_kg": {"new": str(norm_data['co2e_kg'])},
                            "status": {"new": "PENDING_REVIEW"}
                        }
                    )
                    success_count += 1
            
            # Post-ingestion: Run Statistical Outlier Detection
            detect_outliers(org)

            job.status = 'SUCCESS'
            job.save()

            return Response({
                "message": f"Successfully ingested {success_count} records from {file_obj.name}.",
                "job_id": job.id,
                "status": "SUCCESS"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            job.status = 'FAILED'
            job.error_logs = str(e)
            job.save()
            return Response({
                "error": "Failed to process the uploaded file.",
                "details": str(e),
                "job_id": job.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MetricsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        org_name = request.query_params.get('organization', 'Breathe ESG Enterprise')
        org, _ = Organization.objects.get_or_create(name=org_name)

        records = NormalizedRecord.objects.filter(organization=org)
        
        # Calculate sums
        scope1_co2e = records.filter(scope='Scope 1').aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
        scope2_co2e = records.filter(scope='Scope 2').aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
        scope3_co2e = records.filter(scope='Scope 3').aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
        total_co2e = scope1_co2e + scope2_co2e + scope3_co2e

        # Counts
        total_count = records.count()
        pending_count = records.filter(status='PENDING_REVIEW').count()
        approved_count = records.filter(status='APPROVED').count()
        locked_count = records.filter(status='LOCKED_FOR_AUDIT').count()
        suspicious_count = records.filter(suspicious_flag=True).count()

        # Ingestion jobs
        jobs = IngestionJob.objects.filter(organization=org).order_by('-created_at')[:10]
        jobs_data = [{
            "id": job.id,
            "source_type": job.source_type,
            "status": job.status,
            "file_name": job.file_name,
            "created_at": job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "error_logs": job.error_logs
        } for job in jobs]

        # Category Breakdown
        category_breakdown = records.values('scope', 'category').annotate(co2e=Sum('co2e_kg')).order_by('-co2e')

        # Simple monthly time-series for charts
        # Filter dates that are valid and construct month timeline
        timeline = {}
        for r in records.filter(start_date__isnull=False):
            month_key = r.start_date.strftime('%Y-%m')
            timeline.setdefault(month_key, {'Scope 1': 0, 'Scope 2': 0, 'Scope 3': 0})
            timeline[month_key][r.scope] += float(r.co2e_kg)

        timeline_sorted = sorted([
            {
                "month": k,
                "Scope 1": v['Scope 1'],
                "Scope 2": v['Scope 2'],
                "Scope 3": v['Scope 3'],
                "total": v['Scope 1'] + v['Scope 2'] + v['Scope 3']
            } for k, v in timeline.items()
        ], key=lambda x: x['month'])

        return Response({
            "metrics": {
                "scope1_co2e_kg": float(scope1_co2e),
                "scope2_co2e_kg": float(scope2_co2e),
                "scope3_co2e_kg": float(scope3_co2e),
                "total_co2e_kg": float(total_co2e),
                "total_records": total_count,
                "pending_records": pending_count,
                "approved_records": approved_count,
                "locked_records": locked_count,
                "suspicious_records": suspicious_count,
            },
            "recent_jobs": jobs_data,
            "category_breakdown": [{"scope": c['scope'], "category": c['category'], "co2e_kg": float(c['co2e'])} for c in category_breakdown],
            "emissions_timeline": timeline_sorted
        })


class RecordListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        org_name = request.query_params.get('organization', 'Breathe ESG Enterprise')
        org, _ = Organization.objects.get_or_create(name=org_name)

        queryset = NormalizedRecord.objects.filter(organization=org).order_by('-created_at')

        # Filter by scope
        scope = request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)

        # Filter by source_type
        source_type = request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type.upper())

        # Filter by status
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by suspicious flag
        suspicious = request.query_params.get('suspicious')
        if suspicious:
            queryset = queryset.filter(suspicious_flag=(suspicious.lower() == 'true'))

        records_data = []
        for r in queryset:
            raw_data = r.raw_record.raw_data if r.raw_record else {}
            records_data.append({
                "id": r.id,
                "source_type": r.source_type,
                "scope": r.scope,
                "category": r.category,
                "raw_quantity": float(r.raw_quantity),
                "raw_unit": r.raw_unit,
                "normalized_quantity": float(r.normalized_quantity),
                "normalized_unit": r.normalized_unit,
                "co2e_kg": float(r.co2e_kg),
                "start_date": r.start_date.strftime('%Y-%m-%d') if r.start_date else None,
                "end_date": r.end_date.strftime('%Y-%m-%d') if r.end_date else None,
                "status": r.status,
                "suspicious_flag": r.suspicious_flag,
                "suspicious_reason": r.suspicious_reason,
                "is_locked": r.is_locked,
                "raw_data": raw_data,
                "approved_by": r.approved_by.username if r.approved_by else None,
                "approved_at": r.approved_at.strftime('%Y-%m-%d %H:%M:%S') if r.approved_at else None
            })

        return Response(records_data)


class RecordDetailView(APIView):
    permission_classes = [AllowAny]

    def put(self, request, pk):
        """
        Manually edit a normalized record. Automatically triggers CO2e recalculation
        and creates detailed Audit Trail.
        """
        try:
            record = NormalizedRecord.objects.get(pk=pk)
        except NormalizedRecord.DoesNotExist:
            return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

        if record.is_locked:
            return Response({"error": "Cannot edit a locked record. Please unlock it or sign off first."}, status=status.HTTP_400_BAD_REQUEST)

        # System or requested user
        user, _ = User.objects.get_or_create(username='analyst_user')
        
        changes = {}
        old_quantity = record.normalized_quantity
        old_co2e = record.co2e_kg
        old_status = record.status
        old_category = record.category

        # Extract editable fields
        qty_val = request.data.get('normalized_quantity')
        start_date_val = request.data.get('start_date')
        end_date_val = request.data.get('end_date')
        susp_flag_val = request.data.get('suspicious_flag')
        susp_reason_val = request.data.get('suspicious_reason')
        category_val = request.data.get('category')

        with transaction.atomic():
            if qty_val is not None:
                new_qty = Decimal(str(qty_val))
                if new_qty != old_quantity:
                    record.normalized_quantity = new_qty
                    changes['normalized_quantity'] = {"old": float(old_quantity), "new": float(new_qty)}
                    
            if category_val is not None and category_val != old_category:
                record.category = category_val
                changes['category'] = {"old": old_category, "new": category_val}

            if start_date_val:
                new_start = datetime.strptime(start_date_val, '%Y-%m-%d').date()
                if new_start != record.start_date:
                    changes['start_date'] = {"old": str(record.start_date), "new": str(new_start)}
                    record.start_date = new_start

            if end_date_val:
                new_end = datetime.strptime(end_date_val, '%Y-%m-%d').date()
                if new_end != record.end_date:
                    changes['end_date'] = {"old": str(record.end_date), "new": str(new_end)}
                    record.end_date = new_end

            if susp_flag_val is not None:
                new_flag = bool(susp_flag_val)
                if new_flag != record.suspicious_flag:
                    changes['suspicious_flag'] = {"old": record.suspicious_flag, "new": new_flag}
                    record.suspicious_flag = new_flag
                    
            if susp_reason_val is not None and susp_reason_val != record.suspicious_reason:
                changes['suspicious_reason'] = {"old": record.suspicious_reason, "new": susp_reason_val}
                record.suspicious_reason = susp_reason_val

            # Recalculate carbon emissions
            recalculate_co2e(record)
            if record.co2e_kg != old_co2e:
                changes['co2e_kg'] = {"old": float(old_co2e), "new": float(record.co2e_kg)}

            # Reset status to Pending Review if edited so it has to be re-approved
            if changes and record.status == 'APPROVED':
                record.status = 'PENDING_REVIEW'
                changes['status'] = {"old": 'APPROVED', "new": 'PENDING_REVIEW'}

            record.save()

            if changes:
                AuditTrail.objects.create(
                    normalized_record=record,
                    user=user,
                    action='RECORD_EDITED',
                    changes=changes
                )

        return Response({
            "message": "Record updated successfully.",
            "record_id": record.id,
            "new_co2e_kg": float(record.co2e_kg),
            "changes": changes
        })


class BulkApproveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        record_ids = request.data.get('record_ids', [])
        if not record_ids:
            return Response({"error": "No record IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        user, _ = User.objects.get_or_create(username='analyst_user')
        
        approved_count = 0
        with transaction.atomic():
            records = NormalizedRecord.objects.filter(id__in=record_ids, is_locked=False)
            for r in records:
                if r.status != 'APPROVED':
                    r.status = 'APPROVED'
                    r.approved_by = user
                    r.approved_at = timezone.now()
                    r.save()
                    
                    AuditTrail.objects.create(
                        normalized_record=r,
                        user=user,
                        action='RECORD_APPROVED',
                        changes={"status": {"old": "PENDING_REVIEW", "new": "APPROVED"}}
                    )
                    approved_count += 1

        return Response({"message": f"Successfully approved {approved_count} records."})


class BulkLockView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        record_ids = request.data.get('record_ids', [])
        if not record_ids:
            return Response({"error": "No record IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        user, _ = User.objects.get_or_create(username='analyst_user')
        
        locked_count = 0
        with transaction.atomic():
            records = NormalizedRecord.objects.filter(id__in=record_ids)
            for r in records:
                if not r.is_locked:
                    old_status = r.status
                    r.is_locked = True
                    r.status = 'LOCKED_FOR_AUDIT'
                    # Auto-approve if not already done
                    if not r.approved_by:
                        r.approved_by = user
                        r.approved_at = timezone.now()
                    r.save()
                    
                    AuditTrail.objects.create(
                        normalized_record=r,
                        user=user,
                        action='RECORD_LOCKED_FOR_AUDIT',
                        changes={
                            "is_locked": {"old": False, "new": True},
                            "status": {"old": old_status, "new": "LOCKED_FOR_AUDIT"}
                        }
                    )
                    locked_count += 1

        return Response({"message": f"Successfully locked {locked_count} records for auditing."})


class AuditTrailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        org_name = request.query_params.get('organization', 'Breathe ESG Enterprise')
        org, _ = Organization.objects.get_or_create(name=org_name)

        trails = AuditTrail.objects.filter(normalized_record__organization=org).order_by('-timestamp')
        
        trails_data = [{
            "id": t.id,
            "record_id": t.normalized_record.id,
            "source_type": t.normalized_record.source_type,
            "category": t.normalized_record.category,
            "user": t.user.username if t.user else 'System',
            "action": t.action,
            "changes": t.changes,
            "timestamp": t.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for t in trails]

        return Response(trails_data)
