"""
EIA API Testing and Debugging Suite

This is a DIAGNOSTIC TOOL for testing and debugging the EIA API connection.
It does NOT download data for analysis - use download_eia_data.py for that.

Use this script when:
- You're having trouble connecting to the API
- You want to explore available endpoints
- You need to debug API responses
- You want to test API performance/rate limits

Usage:
    python test_eia_api.py

This will run a comprehensive test suite and show detailed debug information.
"""

import requests
import json
import os
import pandas as pd
from datetime import datetime
import time
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configuration
EIA_API_KEY = os.environ.get('EIA_API_KEY')
EIA_API_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"


def test_basic_api_connection():
    """Test basic connectivity to EIA API"""
    print("\n" + "="*60)
    print("Testing Basic API Connection")
    print("="*60)
    
    # Try different API endpoints
    endpoints = [
        {
            "name": "V2 API - Region Data",
            "url": "https://api.eia.gov/v2/electricity/rto/region-data/data/",
            "params": {
                "api_key": EIA_API_KEY,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[respondent][]": "PJM",
                "start": "2024-01-01T00",
                "end": "2024-01-01T05",
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "length": 5
            }
        },
        {
            "name": "V1 API - Series",
            "url": "https://api.eia.gov/series/",
            "params": {
                "api_key": EIA_API_KEY,
                "series_id": "EBA.PJM-ALL.D.H"
            }
        }
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting: {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        print(f"Params: {json.dumps(endpoint['params'], indent=2)}")
        
        try:
            response = requests.get(endpoint['url'], params=endpoint['params'])
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✓ Success! Response structure:")
                print(json.dumps(data, indent=2)[:1000] + "...")
            else:
                print(f"✗ Error: {response.text[:500]}")
                
        except Exception as e:
            print(f"✗ Exception: {e}")


def test_available_endpoints():
    """Explore available EIA API v2 endpoints"""
    print("\n" + "="*60)
    print("Exploring Available API Endpoints")
    print("="*60)
    
    base_endpoints = [
        "https://api.eia.gov/v2/",
        "https://api.eia.gov/v2/electricity/",
        "https://api.eia.gov/v2/electricity/rto/"
    ]
    
    for base_url in base_endpoints:
        print(f"\nChecking: {base_url}")
        try:
            response = requests.get(base_url, params={"api_key": EIA_API_KEY})
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'routes' in data['response']:
                    print("Available routes:")
                    for route in data['response']['routes']:
                        print(f"  - {route['id']}: {route.get('name', 'No name')}")
        except Exception as e:
            print(f"Exception: {e}")


def test_region_data_endpoint():
    """Test the region-data endpoint in detail"""
    print("\n" + "="*60)
    print("Testing Region Data Endpoint")
    print("="*60)
    
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "PJM",
        "facets[type][]": "D",  # D = Demand
        "start": "2024-01-01T00",
        "end": "2024-01-01T23",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 24
    }
    
    print(f"Testing: {EIA_API_URL}")
    print(f"Params: {json.dumps(params, indent=2)}")
    
    try:
        response = requests.get(EIA_API_URL, params=params)
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ Success! Response structure:")
            
            if 'response' in data and 'data' in data['response'] and data['response']['data']:
                records = data['response']['data']
                print(f"Found {len(records)} records")
                
                # Show first few records
                print("\nFirst 3 records:")
                for i, record in enumerate(records[:3]):
                    print(f"\nRecord {i+1}:")
                    print(json.dumps(record, indent=2))
                    
                # Analyze data structure
                if records:
                    print("\nData fields available:")
                    for key in records[0].keys():
                        print(f"  - {key}: {type(records[0][key]).__name__}")
        else:
            print(f"✗ Error: {response.text}")
            
    except Exception as e:
        print(f"✗ Exception: {e}")


def test_different_regions():
    """Test data retrieval for different regions/BAs"""
    print("\n" + "="*60)
    print("Testing Different Regions/BAs")
    print("="*60)
    
    test_regions = ['PJM', 'MISO', 'ERCO', 'SPP', 'CISO']
    
    for region in test_regions:
        params = {
            "api_key": EIA_API_KEY,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": region,
            "facets[type][]": "D",
            "start": "2024-01-01T00",
            "end": "2024-01-01T05",
            "length": 5
        }
        
        print(f"\nTesting {region}...")
        try:
            response = requests.get(EIA_API_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'data' in data['response']:
                    records = data['response']['data']
                    if records:
                        print(f"  ✓ Success: Found {len(records)} records")
                        print(f"  Sample value: {records[0].get('value', 'N/A')} MW at {records[0].get('period', 'N/A')}")
                    else:
                        print(f"  ✗ No data found")
            else:
                print(f"  ✗ Error: Status {response.status_code}")
        except Exception as e:
            print(f"  ✗ Exception: {e}")
        
        time.sleep(0.5)  # Be nice to the API


def test_download_sample_data():
    """Test downloading a sample dataset"""
    print("\n" + "="*60)
    print("Testing Sample Data Download")
    print("="*60)
    
    ba = 'PJM'
    year = 2023
    month = 1
    
    print(f"Downloading {ba} data for {year}-{month:02d}...")
    
    params = {
        'api_key': EIA_API_KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': ba,
        'facets[type][]': 'D',
        'start': f"{year}-{month:02d}-01T00",
        'end': f"{year}-{month:02d}-31T23",
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc',
        'offset': 0,
        'length': 5000
    }
    
    all_data = []
    
    while True:
        try:
            response = requests.get(EIA_API_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'response' in data and 'data' in data['response']:
                records = data['response']['data']
                if not records:
                    break
                
                all_data.extend(records)
                print(f"  Retrieved {len(records)} records (total: {len(all_data)})")
                
                if len(records) < 5000:
                    break
                
                params['offset'] += 5000
                
            else:
                print("  Unexpected response structure")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}")
            break
        
        time.sleep(0.5)
    
    if all_data:
        # Convert to DataFrame for analysis
        df = pd.DataFrame(all_data)
        print(f"\n✓ Successfully downloaded {len(df)} records")
        print("\nDataFrame info:")
        print(df.info())
        print("\nFirst few records:")
        print(df.head())
        
        # Basic statistics
        if 'value' in df.columns:
            print(f"\nDemand statistics:")
            print(f"  Mean: {df['value'].mean():.2f} MW")
            print(f"  Min: {df['value'].min():.2f} MW")
            print(f"  Max: {df['value'].max():.2f} MW")


def test_api_rate_limits():
    """Test API rate limits and response times"""
    print("\n" + "="*60)
    print("Testing API Rate Limits")
    print("="*60)
    
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "PJM",
        "facets[type][]": "D",
        "start": "2024-01-01T00",
        "end": "2024-01-01T00",
        "length": 1
    }
    
    print("Making 10 rapid requests...")
    response_times = []
    
    for i in range(10):
        start_time = time.time()
        try:
            response = requests.get(EIA_API_URL, params=params)
            elapsed = time.time() - start_time
            response_times.append(elapsed)
            print(f"  Request {i+1}: Status {response.status_code}, Time: {elapsed:.2f}s")
        except Exception as e:
            print(f"  Request {i+1}: Error - {e}")
        
        time.sleep(0.1)  # Small delay between requests
    
    if response_times:
        print(f"\nResponse time statistics:")
        print(f"  Average: {sum(response_times)/len(response_times):.2f}s")
        print(f"  Min: {min(response_times):.2f}s")
        print(f"  Max: {max(response_times):.2f}s")


def main():
    """Run all tests"""
    print("EIA API Test Suite")
    print("==================")
    
    if not EIA_API_KEY:
        print("ERROR: EIA_API_KEY not found in environment variables!")
        print("Please set your API key in the .env file")
        return
    
    tests = [
        ("Basic API Connection", test_basic_api_connection),
        ("Available Endpoints", test_available_endpoints),
        ("Region Data Endpoint", test_region_data_endpoint),
        ("Different Regions", test_different_regions),
        ("Sample Data Download", test_download_sample_data),
        ("API Rate Limits", test_api_rate_limits)
    ]
    
    print(f"\nRunning {len(tests)} tests...\n")
    
    for name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\nERROR in {name}: {e}")
        
        print("\n" + "-"*60)
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    main()