#!/usr/bin/env python3
"""
Test script to explore EIA API endpoints for plant location data
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.api import make_eia_request, validate_api_key

# Load environment variables
load_dotenv()


def test_operating_generator_capacity():
    """Test the operating-generator-capacity endpoint"""
    print("\n=== Testing operating-generator-capacity endpoint ===")
    
    endpoint = "electricity/operating-generator-capacity/data/"
    params = {
        'frequency': 'monthly',
        'data[0]': 'nameplate-capacity-mw',
        'start': '2023-01',
        'end': '2023-01',
        'length': 5
    }
    
    response = make_eia_request(endpoint, params)
    
    if response and 'response' in response:
        print(f"Success! Got {len(response['response'].get('data', []))} records")
        
        # Print first record to see available fields
        if response['response'].get('data'):
            print("\nSample record fields:")
            first_record = response['response']['data'][0]
            for key, value in first_record.items():
                print(f"  {key}: {value}")
        
        # Check for any location-related fields
        print("\nLocation-related fields found:")
        location_fields = ['lat', 'lon', 'latitude', 'longitude', 'location', 
                          'address', 'city', 'county', 'zip', 'zipcode']
        for field in location_fields:
            if any(field in str(k).lower() for k in first_record.keys()):
                print(f"  Found: {field}")
    else:
        print("Failed to get data from this endpoint")


def test_state_electricity_profiles():
    """Test the state-electricity-profiles endpoint"""
    print("\n=== Testing state-electricity-profiles endpoint ===")
    
    endpoint = "electricity/state-electricity-profiles/capability-by-fuel/data/"
    params = {
        'frequency': 'annual',
        'data[0]': 'capability',
        'start': '2023',
        'end': '2023',
        'length': 5
    }
    
    response = make_eia_request(endpoint, params)
    
    if response and 'response' in response:
        print(f"Success! Got {len(response['response'].get('data', []))} records")
        
        # Print first record to see available fields
        if response['response'].get('data'):
            print("\nSample record fields:")
            first_record = response['response']['data'][0]
            for key, value in first_record.items():
                print(f"  {key}: {value}")
    else:
        print("Failed to get data from this endpoint")


def test_facility_endpoint():
    """Test the facility endpoint directly for plant details"""
    print("\n=== Testing facility endpoint ===")
    
    endpoint = "electricity/facility/data/"
    params = {
        'frequency': 'annual',
        'data[0]': 'total-net-generation',
        'start': '2023',
        'end': '2023',
        'length': 5
    }
    
    response = make_eia_request(endpoint, params)
    
    if response and 'response' in response:
        print(f"Success! Got {len(response['response'].get('data', []))} records")
        
        # Print first record to see available fields
        if response['response'].get('data'):
            print("\nSample record fields:")
            first_record = response['response']['data'][0]
            for key, value in first_record.items():
                print(f"  {key}: {value}")
                
            # Check for location fields
            print("\nChecking for location-related fields...")
            location_keywords = ['lat', 'lon', 'location', 'address', 'city', 
                               'county', 'zip', 'coord', 'geo']
            found_location_fields = []
            for key in first_record.keys():
                if any(keyword in key.lower() for keyword in location_keywords):
                    found_location_fields.append(key)
            
            if found_location_fields:
                print(f"Found location fields: {found_location_fields}")
            else:
                print("No obvious location fields found")
    else:
        print("Failed to get data from this endpoint")


def test_plant_level_endpoints():
    """Test various plant-level endpoints"""
    print("\n=== Testing various plant-level endpoints ===")
    
    # List of endpoints to test
    endpoints = [
        "electricity/plant-level/data/",
        "electricity/generator/data/",
        "electricity/plant/data/",
        "electricity/power-plants/data/"
    ]
    
    for endpoint in endpoints:
        print(f"\nTrying endpoint: {endpoint}")
        params = {
            'length': 2
        }
        
        response = make_eia_request(endpoint, params)
        
        if response:
            if 'response' in response and 'data' in response['response']:
                print(f"  Success! Got data")
                if response['response']['data']:
                    print("  Sample fields:", list(response['response']['data'][0].keys())[:10])
            else:
                print(f"  Got response but unexpected structure: {list(response.keys())}")
        else:
            print(f"  No response")


def main():
    """Main function to run all tests"""
    
    # Validate API key first
    if not validate_api_key():
        print("API key validation failed!")
        return
    
    print("API key validated successfully!")
    
    # Run all tests
    test_operating_generator_capacity()
    test_state_electricity_profiles()
    test_facility_endpoint()
    test_plant_level_endpoints()
    
    print("\n=== Testing complete ===")


if __name__ == "__main__":
    main()