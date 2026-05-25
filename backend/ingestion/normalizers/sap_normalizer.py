import csv
import io
from datetime import datetime
from decimal import Decimal
from .base import BaseNormalizer, EMISSION_FACTORS

# Mapping of German units to standard keys and factors
SAP_UNIT_MAPPING = {
    'L': ('Liters', 'FUEL_DIESEL_L'),
    'GAL': ('Gallons', 'FUEL_DIESEL_GAL'),
    'M3': ('Cubic Meters', 'FUEL_NATURAL_GAS_M3'),
    'T': ('Tonnes', 'FUEL_LPG_T'),
    'KG': ('Kilograms', 'FUEL_LPG_KG'),
}

# Mapping of cryptic plant codes to names & grid zones
PLANT_LOOKUP = {
    'DE01': ('Germany Plant', 'DE'),
    'US02': ('US Plant', 'US'),
    'IN03': ('India Plant', 'IN'),
}

class SAPNormalizer(BaseNormalizer):
    def parse(self, raw_content, organization_id):
        records = []
        
        # Semicolon is standard for German ALV exports due to decimal comma representation
        delimiter = ';' if ';' in raw_content else ','
        
        csv_file = io.StringIO(raw_content)
        reader = csv.DictReader(csv_file, delimiter=delimiter)
        
        for idx, row in enumerate(reader):
            # Strip whitespace from keys and values
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
            
            # 1. Preservation of exact source of truth (Raw data)
            raw_record_data = row.copy()
            raw_record_data['_line_number'] = idx + 2  # 1-indexed header + 1
            
            suspicious_flag = False
            suspicious_reasons = []
            
            # 2. Key mapping
            bukrs = row.get('BUKRS')
            werks = row.get('WERKS', '')
            budat_str = row.get('BUDAT', '')
            menge_str = row.get('MENGE', '0')
            meins = row.get('MEINS', '').upper()
            wrbtr_str = row.get('WRBTR', '0')
            waers = row.get('WAERS', '')
            sgtxt = row.get('SGTXT', '')

            # Parse Quantity (handle commas as decimals if German configuration is used)
            try:
                menge_cleaned = menge_str.replace(',', '.')
                quantity = Decimal(menge_cleaned)
            except Exception:
                quantity = Decimal('0')
                suspicious_flag = True
                suspicious_reasons.append(f"Invalid quantity format: '{menge_str}'")

            # Parse Posting Date (format: DD.MM.YYYY)
            activity_date = None
            if budat_str:
                for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        activity_date = datetime.strptime(budat_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not activity_date:
                    suspicious_flag = True
                    suspicious_reasons.append(f"Invalid date format: '{budat_str}'. Expected DD.MM.YYYY")
            else:
                suspicious_flag = True
                suspicious_reasons.append("Missing posting date (BUDAT)")

            # Resolve Category & Emission Factors by checking Base Unit and description
            category = 'Stationary Combustion'
            factor_key = None
            normalized_unit = meins
            
            unit_info = SAP_UNIT_MAPPING.get(meins)
            if unit_info:
                normalized_unit, default_factor_key = unit_info
                factor_key = default_factor_key
            else:
                suspicious_flag = True
                suspicious_reasons.append(f"Unknown unit code: '{meins}'")

            # If description matches a specific gas, ensure natural gas factor is mapped
            sgtxt_lower = sgtxt.lower()
            if 'gas' in sgtxt_lower or 'erdgas' in sgtxt_lower:
                category = 'Stationary Combustion - Natural Gas'
                factor_key = 'FUEL_NATURAL_GAS_M3'
            elif 'lpg' in sgtxt_lower or 'propane' in sgtxt_lower:
                category = 'Stationary Combustion - LPG'
                factor_key = 'FUEL_LPG_T' if meins == 'T' else 'FUEL_LPG_KG'
            elif 'diesel' in sgtxt_lower or 'heizoel' in sgtxt_lower or 'oil' in sgtxt_lower:
                category = 'Stationary Combustion - Fuel Oil / Diesel'
                factor_key = 'FUEL_DIESEL_L' if meins == 'L' else 'FUEL_DIESEL_GAL'

            # Plant validation & details
            plant_name = werks
            if werks in PLANT_LOOKUP:
                plant_name, _ = PLANT_LOOKUP[werks]
            else:
                suspicious_flag = True
                suspicious_reasons.append(f"Unrecognized plant code: '{werks}' (No plant location lookup)")

            # Calculate Carbon
            co2e = Decimal('0')
            if factor_key and factor_key in EMISSION_FACTORS:
                factor = Decimal(str(EMISSION_FACTORS[factor_key]))
                co2e = quantity * factor
            else:
                suspicious_flag = True
                suspicious_reasons.append(f"Could not map emission factor for unit {meins} and description")

            # Basic limit flags
            if quantity <= 0:
                suspicious_flag = True
                suspicious_reasons.append(f"Non-positive quantity: {quantity}")

            normalized_record_data = {
                'organization_id': organization_id,
                'source_type': 'SAP',
                'scope': 'Scope 1',
                'category': category,
                'raw_quantity': quantity,
                'raw_unit': meins,
                'normalized_quantity': quantity,
                'normalized_unit': normalized_unit,
                'co2e_kg': co2e,
                'start_date': activity_date,
                'end_date': activity_date,
                'suspicious_flag': suspicious_flag,
                'suspicious_reason': "; ".join(suspicious_reasons) if suspicious_reasons else None,
            }
            
            records.append((raw_record_data, normalized_record_data))
            
        return records
