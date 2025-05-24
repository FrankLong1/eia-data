# EIA Data Fetching Utilities

This directory contains utilities for downloading data from the EIA API, with shared functionality to avoid code duplication.

## Shared Utilities (`eia_utils.py`)

The `eia_utils.py` module provides common functionality used across all EIA data fetching scripts:

### Constants
- `FUEL_TYPES`: Dictionary of fuel type codes and descriptions
- `STATES`: List of US state abbreviations
- `BALANCING_AUTHORITIES`: List of balancing authority codes
- `PRIME_MOVERS`: Dictionary of prime mover codes and descriptions

### Functions

#### `validate_api_key()`
Validates the EIA API key and provides helpful error messages if missing or invalid.
```python
if not validate_api_key():
    return  # Exit if API key is invalid
```

#### `make_eia_request(endpoint, params, timeout=30)`
Makes requests to the EIA API with automatic error handling.
```python
data = make_eia_request("electricity/facility-fuel/data/", params)
if data:
    records = data['response']['data']
```

#### Other Utilities
- `get_state_name(state_code)`: Convert state abbreviation to full name
- `format_date_range(start, end)`: Format date ranges for display
- `parse_plant_filename(filename)`: Extract metadata from plant data filenames

## Using the Utilities

### In Plant Data Scripts
```python
from eia_utils import (
    EIA_API_KEY, FUEL_TYPES, STATES,
    validate_api_key, make_eia_request
)

# Validate API key once
if not validate_api_key():
    return

# Make API requests
data = make_eia_request("electricity/facility-fuel/data/", params)
```

### In BA Data Scripts
```python
from eia_utils import (
    BALANCING_AUTHORITIES,
    validate_api_key, make_eia_request
)

# Use shared BA list
for ba in BALANCING_AUTHORITIES:
    download_ba_data(ba)
```

## Benefits

1. **DRY (Don't Repeat Yourself)**: No duplicate code across scripts
2. **Consistent Error Handling**: All scripts handle API errors the same way
3. **Easy Maintenance**: Update constants or logic in one place
4. **Better Documentation**: Clear, centralized documentation of API codes
5. **Improved Testing**: Can unit test utilities separately

## Adding New Constants

To add new constants (e.g., new fuel types discovered):

1. Edit `eia_utils.py`
2. Add to the appropriate dictionary/list
3. Update `__all__` export if adding new functions
4. All scripts automatically get the update

## Error Handling

The utilities provide consistent error handling:
- Missing API key: Clear instructions on how to get one
- Invalid API key: Validation with test request
- Failed requests: Logging with appropriate error levels
- Malformed responses: Graceful handling with warnings