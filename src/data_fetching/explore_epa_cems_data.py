#!/usr/bin/env python3
"""
EPA CEMS (Continuous Emission Monitoring System) Data Explorer

This script explores the EPA Clean Air Markets API to check if hourly 
"tick" data is available for power plants, particularly those in California.

The EPA CEMS data provides hourly emissions and operational data for 
fossil fuel-fired power plants >= 25 MW capacity.
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# EPA Clean Air Markets API configuration
EPA_API_KEY = os.getenv('EPA_CLEAN_AIR_API_KEY')
EPA_BASE_URL = "https://api.epa.gov/easey"

# API endpoints
FACILITIES_ENDPOINT = f"{EPA_BASE_URL}/facilities-mgmt/facilities"
EMISSIONS_HOURLY_ENDPOINT = f"{EPA_BASE_URL}/emissions-mgmt/emissions/apportioned/hourly"
ATTRIBUTES_ENDPOINT = f"{EPA_BASE_URL}/facilities-mgmt/facilities/attributes"

def test_api_connection():
    """Test if the EPA API key works."""
    print("Testing EPA API connection...")
    
    headers = {
        'x-api-key': EPA_API_KEY,
        'Accept': 'application/json'
    }
    
    # Simple test query
    params = {
        'stateCode': 'CA',
        'page': 1,
        'perPage': 1
    }
    
    try:
        response = requests.get(FACILITIES_ENDPOINT, headers=headers, params=params)
        if response.status_code == 200:
            print("✓ API connection successful!")
            return True
        else:
            print(f"✗ API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def get_california_facilities():
    """Get list of California facilities from EPA database."""
    print("\nFetching California facilities from EPA CEMS...")
    
    headers = {
        'x-api-key': EPA_API_KEY,
        'Accept': 'application/json'
    }
    
    params = {
        'stateCode': 'CA',
        'page': 1,
        'perPage': 100  # Get first 100 facilities
    }
    
    try:
        response = requests.get(FACILITIES_ENDPOINT, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # EPA API might return list directly or wrapped in object
            if isinstance(data, list):
                facilities = data
            else:
                facilities = data.get('facilities', data.get('data', []))
            print(f"Found {len(facilities)} facilities in California")
            
            # Display first few facilities
            print("\nFirst 10 California facilities in EPA CEMS:")
            print("-" * 80)
            for i, facility in enumerate(facilities[:10]):
                print(f"{i+1}. {facility.get('facilityName', 'Unknown')} (ORIS: {facility.get('facilityId', 'N/A')})")
                print(f"   Location: {facility.get('county', 'Unknown County')}, CA")
                print(f"   Status: {facility.get('facilityStatus', 'Unknown')}")
                print()
            
            return facilities
        else:
            print(f"Error fetching facilities: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_hourly_emissions_data(facility_id, start_date, end_date):
    """
    Get hourly emissions data for a specific facility.
    
    Args:
        facility_id: EPA ORIS code for the facility
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    print(f"\nFetching hourly data for facility {facility_id} from {start_date} to {end_date}...")
    
    headers = {
        'x-api-key': EPA_API_KEY,
        'Accept': 'application/json'
    }
    
    params = {
        'facilityId': facility_id,
        'beginDate': start_date,
        'endDate': end_date,
        'page': 1,
        'perPage': 100  # Get first 100 hours
    }
    
    try:
        response = requests.get(EMISSIONS_HOURLY_ENDPOINT, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # EPA API might return list directly or wrapped in object
            if isinstance(data, list):
                emissions_data = data
            else:
                emissions_data = data.get('emissions', data.get('data', []))
            
            if emissions_data:
                print(f"✓ Found {len(emissions_data)} hourly records")
                
                # Convert to DataFrame for easier viewing
                df = pd.DataFrame(emissions_data)
                
                # Display key columns if they exist
                key_columns = ['date', 'hour', 'grossLoad', 'steamLoad', 'co2Mass', 'so2Mass', 'noxMass', 
                              'heatInput', 'unitId', 'stackId']
                available_columns = [col for col in key_columns if col in df.columns]
                
                if available_columns:
                    print("\nSample hourly data (first 10 records):")
                    print("-" * 100)
                    print(df[available_columns].head(10).to_string())
                    
                    # Show data summary
                    if 'grossLoad' in df.columns:
                        print(f"\nGross Load Summary:")
                        print(f"  Min: {df['grossLoad'].min()} MW")
                        print(f"  Max: {df['grossLoad'].max()} MW")
                        print(f"  Mean: {df['grossLoad'].mean():.2f} MW")
                    
                    if 'date' in df.columns and 'hour' in df.columns:
                        print(f"\nTime range: {df['date'].min()} hour {df['hour'].min()} to {df['date'].max()} hour {df['hour'].max()}")
                
                return df
            else:
                print("No hourly data found for this facility in the specified date range")
                return pd.DataFrame()
        else:
            print(f"Error fetching hourly data: {response.status_code} - {response.text}")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()

def match_eia_to_epa(eia_plant_id, plant_name):
    """
    Try to match an EIA plant to EPA ORIS code.
    Note: This is a simple name-based match; in practice, you'd use crosswalk files.
    """
    print(f"\nSearching for EPA match for EIA plant {eia_plant_id}: {plant_name}")
    
    headers = {
        'x-api-key': EPA_API_KEY,
        'Accept': 'application/json'
    }
    
    # Search by partial name match
    search_name = plant_name.split()[0] if plant_name else ""
    
    params = {
        'stateCode': 'CA',
        'facilityName': search_name,
        'page': 1,
        'perPage': 10
    }
    
    try:
        response = requests.get(FACILITIES_ENDPOINT, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # EPA API might return list directly or wrapped in object
            if isinstance(data, list):
                facilities = data
            else:
                facilities = data.get('facilities', data.get('data', []))
            
            if facilities:
                print(f"Potential matches found:")
                for facility in facilities:
                    print(f"  - {facility.get('facilityName')} (ORIS: {facility.get('facilityId')})")
                return facilities[0].get('facilityId') if facilities else None
            else:
                print("No matches found")
                return None
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    """Main function to explore EPA CEMS data."""
    print("=" * 80)
    print("EPA CEMS Hourly Data Explorer")
    print("=" * 80)
    
    # Test API connection
    if not test_api_connection():
        print("Failed to connect to EPA API. Please check your API key.")
        return
    
    # Get California facilities
    ca_facilities = get_california_facilities()
    
    if ca_facilities:
        # Pick a facility to test hourly data
        test_facility = ca_facilities[0]  # First facility
        facility_id = test_facility.get('facilityId')
        facility_name = test_facility.get('facilityName', 'Unknown')
        
        print(f"\n" + "=" * 80)
        print(f"Testing hourly data retrieval for: {facility_name} (ORIS: {facility_id})")
        print("=" * 80)
        
        # Get recent data (Q1 2025 since API says data available through Q1 2025)
        end_date = datetime(2025, 3, 31).date()
        start_date = datetime(2025, 3, 1).date()
        
        hourly_data = get_hourly_emissions_data(
            facility_id,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not hourly_data.empty:
            print("\n✓ SUCCESS! Hourly 'tick' data is available from EPA CEMS!")
            print("\nKey findings:")
            print("- EPA CEMS provides hourly gross load (MW) data")
            print("- Also includes hourly emissions (CO2, SO2, NOx)")
            print("- Data available for fossil fuel plants >= 25 MW")
            print("- Covers most large thermal power plants")
            
            # Try a specific date range with more data
            print(f"\n" + "=" * 80)
            print("Fetching full month of data for analysis...")
            print("=" * 80)
            
            # Get data for January 2024
            monthly_data = get_hourly_emissions_data(
                facility_id,
                '2024-01-01',
                '2024-01-31'
            )
            
            if not monthly_data.empty:
                # Save sample data
                output_file = 'epa_cems_hourly_sample.csv'
                monthly_data.to_csv(output_file, index=False)
                print(f"\nSaved sample hourly data to: {output_file}")
        
        # Try to match with EIA data
        print(f"\n" + "=" * 80)
        print("Testing EIA-EPA plant matching...")
        print("=" * 80)
        
        # Load a sample California plant from EIA data
        plant_lookup = pd.read_csv('plant_data/plant_lookup.csv', dtype={'plant_id': str})
        ca_plants = plant_lookup[plant_lookup['state'] == 'CA'].head(5)
        
        print(f"\nTrying to match {len(ca_plants)} California plants from EIA to EPA ORIS codes:")
        for _, plant in ca_plants.iterrows():
            epa_id = match_eia_to_epa(plant['plant_id'], plant['plant_name'])
            if epa_id:
                print(f"\n✓ Potential match found for {plant['plant_name']}")
                # Get some hourly data for this plant
                test_data = get_hourly_emissions_data(epa_id, '2024-01-01', '2024-01-01')

    print("\n" + "=" * 80)
    print("Summary: EPA CEMS provides genuine hourly 'tick' data for power plants!")
    print("This includes hourly gross load (MW) and emissions data.")
    print("=" * 80)

if __name__ == "__main__":
    main()