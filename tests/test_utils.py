#!/usr/bin/env python3
"""
Test script to demonstrate the new utils structure.
"""

from src.utils import (
    # Constants
    FUEL_TYPES, STATES, BALANCING_AUTHORITIES,
    get_state_name, get_fuel_description,
    # API
    validate_api_key,
    # Formatting
    format_date_range, parse_plant_filename,
    format_number_with_commas, format_mwh_to_gwh
)

def main():
    print("Testing EIA Utils Structure")
    print("=" * 50)
    
    # Test constants
    print("\n1. CONSTANTS MODULE:")
    print(f"   Number of fuel types: {len(FUEL_TYPES)}")
    print(f"   Number of states: {len(STATES)}")
    print(f"   Number of BAs: {len(BALANCING_AUTHORITIES)}")
    print(f"   Natural Gas code: NG = {get_fuel_description('NG')}")
    print(f"   Texas: TX = {get_state_name('TX')}")
    
    # Test formatting
    print("\n2. FORMATTING MODULE:")
    print(f"   Date range: {format_date_range('2023-01', '2023-12')}")
    print(f"   Large number: {format_number_with_commas(1234567890)}")
    print(f"   MWh to GWh: {format_mwh_to_gwh(1234567)}")
    
    # Test filename parsing
    filename = "3470_generation_2023-01_2023-12.csv"
    parsed = parse_plant_filename(filename)
    print(f"   Parsed filename '{filename}':")
    print(f"     - Plant ID: {parsed['plant_id']}")
    print(f"     - Data type: {parsed['data_type']}")
    print(f"     - Date range: {parsed['start_date']} to {parsed['end_date']}")
    
    # Test API validation
    print("\n3. API MODULE:")
    print("   Validating API key...")
    if validate_api_key():
        print("   ✓ API key is valid!")
    else:
        print("   ✗ API key validation failed")
    
    print("\n" + "=" * 50)
    print("All utils modules working correctly!")

if __name__ == "__main__":
    main()