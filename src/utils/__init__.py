"""
Utility modules for the EIA data pipeline.

This package contains shared utilities used across the project:
- constants: EIA API constants and mappings
- api: API validation and request handling
- formatting: Data formatting and parsing utilities
"""

from .constants import (
    FUEL_TYPES,
    STATES,
    STATE_NAMES,
    BALANCING_AUTHORITIES,
    PRIME_MOVERS,
    BA_MAPPING,
    EIA860_URL_PATTERN,
    get_state_name,
    get_eia_respondent_name,
    get_fuel_description,
    get_prime_mover_description
)

from .api import (
    EIA_API_KEY,
    EIA_BASE_URL,
    validate_api_key,
    check_api_key,
    make_eia_request
)

from .formatting import (
    format_date_range,
    parse_plant_filename,
    format_number_with_commas,
    parse_date_string
)

__all__ = [
    # Constants
    'FUEL_TYPES',
    'STATES',
    'STATE_NAMES',
    'BALANCING_AUTHORITIES',
    'PRIME_MOVERS',
    'BA_MAPPING',
    'EIA860_URL_PATTERN',
    'get_state_name',
    'get_eia_respondent_name',
    'get_fuel_description',
    'get_prime_mover_description',
    # API
    'EIA_API_KEY',
    'EIA_BASE_URL',
    'validate_api_key',
    'check_api_key',
    'make_eia_request',
    # Formatting
    'format_date_range',
    'parse_plant_filename',
    'format_number_with_commas',
    'parse_date_string'
]