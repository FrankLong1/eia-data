"""
EIA API constants and mappings.

This module contains all constant values used throughout the EIA data pipeline,
including fuel types, state codes, balancing authorities, and various mappings.
"""

# Common fuel types for filtering
FUEL_TYPES = {
    'NG': 'Natural Gas',
    'COL': 'Coal', 
    'NUC': 'Nuclear',
    'SUN': 'Solar',
    'WND': 'Wind',
    'WAT': 'Hydro',
    'OIL': 'Oil',
    'GEO': 'Geothermal',
    'BIO': 'Biomass',
    'OTH': 'Other',
    'LIG': 'Lignite Coal',
    'SUB': 'Subbituminous Coal',
    'BIT': 'Bituminous Coal',
    'PC': 'Petroleum Coke',
    'WDS': 'Wood/Wood Waste',
    'MWH': 'Electricity (for storage)',
    'ALL': 'Total (All Fuels)'
}

# State abbreviations
STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

# State names mapping
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming'
}

# Balancing Authority codes (from the research paper)
BALANCING_AUTHORITIES = [
    # RTOs/ISOs
    'PJM',   # PJM Interconnection
    'MISO',  # Midcontinent ISO
    'ERCO',  # ERCOT (Texas)
    'SWPP',  # Southwest Power Pool
    'CISO',  # California ISO
    'ISNE',  # ISO New England
    'NYIS',  # New York ISO
    
    # Utilities
    'SOCO',  # Southern Company
    'DUK',   # Duke Energy Carolinas
    'CPLE',  # Duke Energy Progress
    'FPC',   # Duke Energy Florida
    'TVA',   # Tennessee Valley Authority
    'BPAT',  # Bonneville Power Administration
    'AZPS',  # Arizona Public Service
    'FPL',   # Florida Power & Light
    'PACE',  # PacifiCorp East
    'PACW',  # PacifiCorp West
    'PGE',   # Portland General Electric
    'PSCO',  # Public Service Company of Colorado
    'SRP',   # Salt River Project
    'SCEG',  # South Carolina Electric & Gas
    'SC',    # Santee Cooper
]

# Mapping of paper acronyms to official EIA respondent names
BA_MAPPING = {
    'CPLE': 'DEP',    # Duke Energy Progress East
    'DUK': 'DEC',     # Duke Energy Carolinas
    'SC': 'SCP',      # Santee Cooper
    'SWPP': 'SPP',    # Southwest Power Pool
    'SCEG': 'DESC',   # Dominion Energy South Carolina
    'FPC': 'DEF',     # Duke Energy Florida
    'CISO': 'CAISO',  # California ISO
    'BPAT': 'BPA',    # Bonneville Power Administration
    'NYIS': 'NYISO',  # New York ISO
    'ERCO': 'ERCOT',  # Texas
    'ISNE': 'ISO-NE'  # New England
}

# Prime mover codes
PRIME_MOVERS = {
    'BA': 'Battery',
    'CA': 'Combined Cycle Combustion Turbine Part',
    'CC': 'Combined Cycle Total',
    'CE': 'Compressed Air Energy Storage',
    'CP': 'Concentrated Solar Power',
    'CS': 'Combined Cycle Single Shaft',
    'CT': 'Combustion Turbine',
    'FW': 'Flywheel',
    'GT': 'Gas Turbine',
    'HA': 'Hydrokinetic - Axial Flow',
    'HB': 'Hydrokinetic - Wave Buoy',
    'HK': 'Hydrokinetic - Other',
    'HY': 'Hydraulic Turbine',
    'IC': 'Internal Combustion',
    'PS': 'Pumped Storage',
    'PV': 'Photovoltaic',
    'ST': 'Steam Turbine',
    'WT': 'Wind Turbine',
    'OT': 'Other',
    'ALL': 'All Types'
}

# EIA-860 data URL pattern
EIA860_URL_PATTERN = "https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"

# Getter functions
def get_state_name(state_code: str) -> str:
    """
    Get full state name from abbreviation.
    
    Args:
        state_code: Two-letter state abbreviation
        
    Returns:
        Full state name, or original code if not found
    """
    return STATE_NAMES.get(state_code, state_code)


def get_eia_respondent_name(ba_code: str) -> str:
    """
    Convert balancing authority code to EIA respondent name.
    
    Args:
        ba_code: Balancing authority code from paper
        
    Returns:
        EIA respondent name, or original code if not mapped
    """
    return BA_MAPPING.get(ba_code, ba_code)


def get_fuel_description(fuel_code: str) -> str:
    """
    Get fuel type description from code.
    
    Args:
        fuel_code: Fuel type code
        
    Returns:
        Fuel description, or original code if not found
    """
    return FUEL_TYPES.get(fuel_code, fuel_code)


def get_prime_mover_description(pm_code: str) -> str:
    """
    Get prime mover description from code.
    
    Args:
        pm_code: Prime mover code
        
    Returns:
        Prime mover description, or original code if not found
    """
    return PRIME_MOVERS.get(pm_code, pm_code)