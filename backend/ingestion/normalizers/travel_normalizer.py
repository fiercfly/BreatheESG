import json
from datetime import datetime
from decimal import Decimal
from .base import BaseNormalizer, EMISSION_FACTORS, AIRPORT_COORDINATES, calculate_haversine_distance

class TravelNormalizer(BaseNormalizer):
    def parse(self, raw_content, organization_id):
        # raw_content can be a JSON string or already parsed list
        if isinstance(raw_content, str):
            try:
                data = json.loads(raw_content)
            except Exception as e:
                raise ValueError(f"Invalid JSON format for Travel Ingestion: {e}")
        else:
            data = raw_content

        records = []
        for idx, item in enumerate(data):
            raw_record_data = item.copy()
            raw_record_data['_index'] = idx
            
            suspicious_flag = False
            suspicious_reasons = []
            
            trip_id = item.get('trip_id', '')
            passenger_name = item.get('passenger_name', '')
            travel_type = item.get('type', '')
            date_str = item.get('date', '')
            details = item.get('details', {})
            
            # Parse Date
            activity_date = None
            if date_str:
                try:
                    activity_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    suspicious_flag = True
                    suspicious_reasons.append(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD")
            else:
                suspicious_flag = True
                suspicious_reasons.append("Missing transaction date")

            # Initialize normalized values
            category = f"Business Travel - {travel_type}"
            raw_quantity = Decimal('0')
            raw_unit = ''
            normalized_quantity = Decimal('0')
            normalized_unit = ''
            co2e = Decimal('0')
            start_date = activity_date
            end_date = activity_date

            if travel_type == 'Flight':
                dep = details.get('departure_airport', '').upper().strip()
                arr = details.get('arrival_airport', '').upper().strip()
                booking_class = details.get('booking_class', 'Economy')
                dist_val = details.get('distance_miles')
                
                raw_unit = 'miles'
                normalized_unit = 'miles'

                # Calculate or lookup distance
                distance = Decimal('0')
                if dist_val is not None:
                    try:
                        distance = Decimal(str(dist_val))
                    except Exception:
                        suspicious_flag = True
                        suspicious_reasons.append(f"Invalid distance value: '{dist_val}'")
                
                # Haversine coordinate-based fallback if distance is missing
                if distance <= 0:
                    if dep in AIRPORT_COORDINATES and arr in AIRPORT_COORDINATES:
                        lat1, lon1 = AIRPORT_COORDINATES[dep]
                        lat2, lon2 = AIRPORT_COORDINATES[arr]
                        computed_dist = calculate_haversine_distance(lat1, lon1, lat2, lon2)
                        distance = Decimal(f"{computed_dist:.2f}")
                        suspicious_reasons.append(f"Distance was missing. Calculated Great-Circle distance between {dep} and {arr}: {distance} miles")
                    else:
                        distance = Decimal('500.00')  # fallback default
                        suspicious_flag = True
                        suspicious_reasons.append(f"Missing flight distance and coordinates for {dep} or {arr}. Used default fallback of 500 miles")

                raw_quantity = distance
                normalized_quantity = distance

                # Determine flight range type
                is_long_haul = distance >= 500
                
                # Find appropriate emission factor
                factor_key = 'FLIGHT_LONG_HAUL_ECONOMY'
                if is_long_haul:
                    if booking_class == 'Business':
                        factor_key = 'FLIGHT_LONG_HAUL_BUSINESS'
                    elif booking_class == 'First':
                        factor_key = 'FLIGHT_LONG_HAUL_FIRST'
                    else:
                        factor_key = 'FLIGHT_LONG_HAUL_ECONOMY'
                else:
                    if booking_class == 'Business' or booking_class == 'First':
                        factor_key = 'FLIGHT_SHORT_HAUL_BUSINESS'
                    else:
                        factor_key = 'FLIGHT_SHORT_HAUL_ECONOMY'

                factor = Decimal(str(EMISSION_FACTORS[factor_key]))
                co2e = distance * factor
                category = f"Business Travel - Flight ({booking_class} Class)"

            elif travel_type == 'Hotel':
                hotel_name = details.get('hotel_name', '')
                loc = details.get('location', '').upper().strip()
                nights_val = details.get('nights', 1)
                rooms_val = details.get('rooms', 1)
                
                raw_unit = 'room-nights'
                normalized_unit = 'room-nights'
                
                try:
                    nights = Decimal(str(nights_val))
                    rooms = Decimal(str(rooms_val))
                    room_nights = nights * rooms
                except Exception:
                    room_nights = Decimal('1')
                    suspicious_flag = True
                    suspicious_reasons.append("Invalid nights or rooms value")

                raw_quantity = room_nights
                normalized_quantity = room_nights
                
                # Calculate hotel duration
                if activity_date:
                    try:
                        from datetime import timedelta
                        end_date = activity_date + timedelta(days=int(nights_val))
                    except Exception:
                        pass

                # Hotel factor lookup
                factor_key = 'HOTEL_DEFAULT'
                if loc == 'USA' or loc == 'US':
                    factor_key = 'HOTEL_USA'
                elif loc == 'DE' or loc == 'GERMANY':
                    factor_key = 'HOTEL_DE'
                elif loc == 'AUS' or loc == 'AUSTRALIA':
                    factor_key = 'HOTEL_AUS'
                elif loc == 'GBR' or loc == 'UK':
                    factor_key = 'HOTEL_GBR'
                
                factor = Decimal(str(EMISSION_FACTORS[factor_key]))
                co2e = room_nights * factor
                category = f"Business Travel - Hotel Stay ({hotel_name})"

            elif travel_type == 'CarRental':
                vehicle_class = details.get('vehicle_class', 'Compact')
                fuel_type = details.get('fuel_type', 'Gasoline')
                dist_val = details.get('distance_miles', 0)
                
                raw_unit = 'miles'
                normalized_unit = 'miles'

                try:
                    distance = Decimal(str(dist_val))
                except Exception:
                    distance = Decimal('0')
                    suspicious_flag = True
                    suspicious_reasons.append("Invalid car rental distance")

                raw_quantity = distance
                normalized_quantity = distance

                factor_key = 'CAR_COMPACT_GAS'
                if fuel_type == 'Electric':
                    factor_key = 'CAR_ELECTRIC'
                elif vehicle_class == 'SUV':
                    factor_key = 'CAR_SUV_GAS'
                
                factor = Decimal(str(EMISSION_FACTORS[factor_key]))
                co2e = distance * factor
                category = f"Business Travel - Car Rental ({vehicle_class} {fuel_type})"
            
            else:
                suspicious_flag = True
                suspicious_reasons.append(f"Unrecognized travel type: '{travel_type}'")

            normalized_record_data = {
                'organization_id': organization_id,
                'source_type': 'TRAVEL',
                'scope': 'Scope 3',
                'category': category,
                'raw_quantity': raw_quantity,
                'raw_unit': raw_unit,
                'normalized_quantity': normalized_quantity,
                'normalized_unit': normalized_unit,
                'co2e_kg': co2e,
                'start_date': start_date,
                'end_date': end_date,
                'suspicious_flag': suspicious_flag,
                'suspicious_reason': "; ".join(suspicious_reasons) if suspicious_reasons else None,
            }

            records.append((raw_record_data, normalized_record_data))
            
        return records
