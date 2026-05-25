import csv
import io
from datetime import datetime
from decimal import Decimal
from .base import BaseNormalizer, EMISSION_FACTORS

# Map Meter ID prefixes to grid mixes
METER_REGION_LOOKUP = {
    'M-98': ('Germany Facility', 'GRID_DE'),
    'M-44': ('US Facility', 'GRID_US'),
    'M-11': ('India Facility', 'GRID_IN'),
}

class UtilityNormalizer(BaseNormalizer):
    def parse(self, raw_content, organization_id):
        records = []
        csv_file = io.StringIO(raw_content)
        reader = csv.DictReader(csv_file)
        
        for idx, row in enumerate(reader):
            # Strip whitespace
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
            
            raw_record_data = row.copy()
            raw_record_data['_line_number'] = idx + 2
            
            suspicious_flag = False
            suspicious_reasons = []
            
            account_num = row.get('Account Number', '')
            meter_id = row.get('Meter ID', '')
            start_date_str = row.get('Billing Start Date', '')
            end_date_str = row.get('Billing End Date', '')
            usage_str = row.get('Usage (kWh)', '0')
            tariff_str = row.get('Tariff Rate', '0')
            
            # Clean comments out of usage (like our suspicious sample which has total amounts like "2775.00 (Suspicious Outlier)")
            # Let's clean the usage string: extract digits and dots only
            usage_cleaned = ''.join(c for c in usage_str if c.isdigit() or c == '.')
            try:
                usage = Decimal(usage_cleaned)
            except Exception:
                usage = Decimal('0')
                suspicious_flag = True
                suspicious_reasons.append(f"Invalid usage format: '{usage_str}'")

            # Parse Start Date
            start_date = None
            if start_date_str:
                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
                    try:
                        start_date = datetime.strptime(start_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not start_date:
                    suspicious_flag = True
                    suspicious_reasons.append(f"Invalid billing start date: '{start_date_str}'")
            else:
                suspicious_flag = True
                suspicious_reasons.append("Missing billing start date")

            # Parse End Date
            end_date = None
            if end_date_str:
                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
                    try:
                        end_date = datetime.strptime(end_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not end_date:
                    suspicious_flag = True
                    suspicious_reasons.append(f"Invalid billing end date: '{end_date_str}'")
            else:
                suspicious_flag = True
                suspicious_reasons.append("Missing billing end date")

            # Validate date range and duration
            billing_days = 0
            if start_date and end_date:
                if end_date < start_date:
                    suspicious_flag = True
                    suspicious_reasons.append(f"End date ({end_date}) is before start date ({start_date})")
                else:
                    billing_days = (end_date - start_date).days
                    # Standard monthly billing is ~28-33 days. Alert if anomalous period!
                    if billing_days < 15:
                        suspicious_flag = True
                        suspicious_reasons.append(f"Anomalously short billing period: {billing_days} days")
                    elif billing_days > 45:
                        suspicious_flag = True
                        suspicious_reasons.append(f"Anomalously long billing period: {billing_days} days")

            # Region/Grid lookup based on Meter ID prefix
            facility_name = "Default Global Facility"
            grid_factor_key = 'GRID_DEFAULT'
            for prefix, (fac_name, key) in METER_REGION_LOOKUP.items():
                if meter_id.startswith(prefix):
                    facility_name = fac_name
                    grid_factor_key = key
                    break

            grid_factor = Decimal(str(EMISSION_FACTORS[grid_factor_key]))
            co2e = usage * grid_factor

            # Limit and sanity flags
            if usage <= 0:
                suspicious_flag = True
                suspicious_reasons.append(f"Non-positive energy consumption: {usage} kWh")

            normalized_record_data = {
                'organization_id': organization_id,
                'source_type': 'UTILITY',
                'scope': 'Scope 2',
                'category': 'Purchased Electricity',
                'raw_quantity': usage,
                'raw_unit': 'kWh',
                'normalized_quantity': usage,
                'normalized_unit': 'kWh',
                'co2e_kg': co2e,
                'start_date': start_date,
                'end_date': end_date,
                'suspicious_flag': suspicious_flag,
                'suspicious_reason': "; ".join(suspicious_reasons) if suspicious_reasons else None,
            }
            
            records.append((raw_record_data, normalized_record_data))
            
        return records
