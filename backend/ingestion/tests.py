from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Organization, IngestionJob, RawRecord, NormalizedRecord, AuditTrail
from .normalizers import SAPNormalizer, UtilityNormalizer, TravelNormalizer
from .views import detect_outliers, recalculate_co2e

class NormalizerTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.system_user = User.objects.create(username="system_user")

    def test_sap_normalizer(self):
        csv_content = """BUKRS;WERKS;BUDAT;MENGE;MEINS;WRBTR;WAERS;SGTXT
1000;DE01;12.04.2026;1500.00;L;1850.00;EUR;Heizoel fuer Notstromaggregat
1000;IN03;20.04.2026;10.00;T;45000.00;INR;LPG cylinder supply
"""
        normalizer = SAPNormalizer()
        parsed = normalizer.parse(csv_content, self.org.id)
        
        self.assertEqual(len(parsed), 2)
        
        # Test First Row: DE01 Heizöl (Diesel) - 1500 L
        raw1, norm1 = parsed[0]
        self.assertEqual(norm1['source_type'], 'SAP')
        self.assertEqual(norm1['scope'], 'Scope 1')
        self.assertEqual(norm1['category'], 'Stationary Combustion - Fuel Oil / Diesel')
        self.assertEqual(norm1['normalized_quantity'], Decimal('1500.00'))
        self.assertEqual(norm1['normalized_unit'], 'Liters')
        # 1500 * 2.68 = 4020
        self.assertEqual(norm1['co2e_kg'], Decimal('4020.00'))
        self.assertEqual(norm1['suspicious_flag'], False)

        # Test Second Row: IN03 LPG - 10 T
        raw2, norm2 = parsed[1]
        self.assertEqual(norm2['scope'], 'Scope 1')
        self.assertEqual(norm2['category'], 'Stationary Combustion - LPG')
        self.assertEqual(norm2['normalized_quantity'], Decimal('10.00'))
        self.assertEqual(norm2['normalized_unit'], 'Tonnes')
        # 10 * 2939.00 = 29390.00
        self.assertEqual(norm2['co2e_kg'], Decimal('29390.00'))

    def test_utility_normalizer(self):
        csv_content = """Account Number,Meter ID,Billing Start Date,Billing End Date,Usage (kWh),Tariff Rate,Total Amount ($)
948172635,M-98273,2026-04-12,2026-05-11,5120,0.14,716.80
"""
        normalizer = UtilityNormalizer()
        parsed = normalizer.parse(csv_content, self.org.id)
        
        self.assertEqual(len(parsed), 1)
        raw, norm = parsed[0]
        self.assertEqual(norm['source_type'], 'UTILITY')
        self.assertEqual(norm['scope'], 'Scope 2')
        self.assertEqual(norm['category'], 'Purchased Electricity')
        self.assertEqual(norm['normalized_quantity'], Decimal('5120'))
        # Germany plant (M-98 prefix): grid mix factor = 0.38 kg/kWh
        # 5120 * 0.38 = 1945.6
        self.assertEqual(norm['co2e_kg'], Decimal('1945.60'))
        self.assertEqual(norm['suspicious_flag'], False)

    def test_travel_normalizer_flights_and_haversine(self):
        # Concur-like travel JSON
        travel_json = [
            {
                "trip_id": "T-1001",
                "passenger_name": "Alice Smith",
                "type": "Flight",
                "date": "2026-04-05",
                "details": {
                    "departure_airport": "SFO",
                    "arrival_airport": "JFK",
                    "booking_class": "Business",
                    "distance_miles": None
                }
            },
            {
                "trip_id": "T-1003",
                "passenger_name": "Alice Smith",
                "type": "Hotel",
                "date": "2026-04-06",
                "details": {
                    "hotel_name": "Grand Hyatt New York",
                    "location": "USA",
                    "nights": 4,
                    "rooms": 1
                }
            }
        ]
        
        normalizer = TravelNormalizer()
        parsed = normalizer.parse(travel_json, self.org.id)
        
        self.assertEqual(len(parsed), 2)
        
        # Test Flight with Haversine fallback (SFO -> JFK)
        raw_flight, norm_flight = parsed[0]
        self.assertEqual(norm_flight['source_type'], 'TRAVEL')
        self.assertEqual(norm_flight['scope'], 'Scope 3')
        self.assertIn("Flight (Business Class)", norm_flight['category'])
        # Distance should be calculated using coordinates (~2586 miles)
        self.assertGreater(norm_flight['normalized_quantity'], Decimal('2500'))
        self.assertLess(norm_flight['normalized_quantity'], Decimal('2650'))
        # CO2e should be computed with Long Haul Business multiplier (0.43 per mile)
        expected_co2e = norm_flight['normalized_quantity'] * Decimal('0.43')
        self.assertAlmostEqual(float(norm_flight['co2e_kg']), float(expected_co2e), places=1)

        # Test Hotel stay in USA (4 room-nights)
        raw_hotel, norm_hotel = parsed[1]
        self.assertEqual(norm_hotel['scope'], 'Scope 3')
        self.assertIn("Hotel Stay", norm_hotel['category'])
        self.assertEqual(norm_hotel['normalized_quantity'], Decimal('4'))
        # 4 room-nights * 18.5 (USA factor) = 74.0 kg CO2e
        self.assertEqual(norm_hotel['co2e_kg'], Decimal('74.00'))

    def test_outlier_detection(self):
        # Create a series of records in the same category
        # Category: Purchased Electricity
        for i in range(5):
            NormalizedRecord.objects.create(
                organization=self.org,
                source_type='UTILITY',
                scope='Scope 2',
                category='Purchased Electricity',
                raw_quantity=Decimal('1000'),
                raw_unit='kWh',
                normalized_quantity=Decimal('1000'),
                normalized_unit='kWh',
                co2e_kg=Decimal('380'), # Standard DE Grid Mix: 1000 * 0.38
                status='PENDING_REVIEW'
            )
            
        # Create an extreme outlier (10x normal value)
        outlier = NormalizedRecord.objects.create(
            organization=self.org,
            source_type='UTILITY',
            scope='Scope 2',
            category='Purchased Electricity',
            raw_quantity=Decimal('10000'),
            raw_unit='kWh',
            normalized_quantity=Decimal('10000'),
            normalized_unit='kWh',
            co2e_kg=Decimal('3800'),
            status='PENDING_REVIEW'
        )

        detect_outliers(self.org)
        
        # Reload outlier
        outlier.refresh_from_db()
        self.assertEqual(outlier.suspicious_flag, True)
        self.assertIn("Statistical Outlier", outlier.suspicious_reason)
