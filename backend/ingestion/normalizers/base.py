import math

# Emission Factors (in kg CO2e per unit)
EMISSION_FACTORS = {
    # Scope 1 - Fuels
    'FUEL_DIESEL_L': 2.68,       # kg CO2e per Liter
    'FUEL_DIESEL_GAL': 10.15,     # kg CO2e per Gallon (US)
    'FUEL_NATURAL_GAS_M3': 2.02,  # kg CO2e per cubic meter
    'FUEL_LPG_T': 2939.00,        # kg CO2e per Metric Tonne
    'FUEL_LPG_KG': 2.939,         # kg CO2e per kg

    # Scope 2 - Electricity (Grid Mixes by Plant Location)
    'GRID_DE': 0.38,   # Germany (kg CO2e per kWh)
    'GRID_US': 0.37,   # United States (kg CO2e per kWh)
    'GRID_IN': 0.72,   # India (kg CO2e per kWh)
    'GRID_DEFAULT': 0.40, # Default global average (kg CO2e per kWh)

    # Scope 3 - Travel: Flights (kg CO2e per passenger-mile)
    'FLIGHT_SHORT_HAUL_ECONOMY': 0.22,
    'FLIGHT_SHORT_HAUL_BUSINESS': 0.33,
    'FLIGHT_LONG_HAUL_ECONOMY': 0.15,
    'FLIGHT_LONG_HAUL_BUSINESS': 0.43,
    'FLIGHT_LONG_HAUL_FIRST': 0.60,

    # Scope 3 - Travel: Hotels (kg CO2e per room-night)
    'HOTEL_USA': 18.5,
    'HOTEL_DE': 12.2,
    'HOTEL_AUS': 24.8,
    'HOTEL_GBR': 11.8,
    'HOTEL_DEFAULT': 15.0,

    # Scope 3 - Travel: Car Rental (kg CO2e per mile)
    'CAR_SUV_GAS': 0.35,
    'CAR_COMPACT_GAS': 0.22,
    'CAR_ELECTRIC': 0.08,
}

# Airport coordinates database (Latitude, Longitude) for distance calculation fallback
AIRPORT_COORDINATES = {
    'SFO': (37.6190, -122.3749),
    'JFK': (40.6398, -73.7789),
    'LAX': (33.9416, -118.4085),
    'LHR': (51.4700, -0.4543),
    'CDG': (49.0097, 2.5479),
    'SYD': (-33.9461, 151.1772),
    'SIN': (1.3644, 103.9915),
    'DXB': (25.2532, 55.3657),
    'HND': (35.5494, 139.7798),
    'CDG': (49.0097, 2.5479),
}

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth in miles.
    """
    R = 3958.8  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

class BaseNormalizer:
    def parse(self, raw_content, organization_id):
        """
        Parse raw content (file contents or JSON data) and return a list of:
        (raw_record_dict, normalized_record_dict) tuples.
        """
        raise NotImplementedError("Subclasses must implement parse()")
