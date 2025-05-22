import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_eia_endpoints():
    """Test various EIA API v2 endpoints to find the correct one for hourly demand data"""
    
    api_key = os.environ.get('EIA_API_KEY')
    
    # Test endpoints based on the search results
    test_configs = [
        {
            "name": "region-sub-ba-data endpoint",
            "url": "https://api.eia.gov/v2/electricity/rto/region-sub-ba-data/data/",
            "params": {
                "api_key": api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[parent][]": "PJM",
                "start": "2024-01-01",
                "end": "2024-01-01",
                "length": 5
            }
        },
        {
            "name": "Try without /data suffix",
            "url": "https://api.eia.gov/v2/electricity/rto/region-sub-ba-data",
            "params": {
                "api_key": api_key,
                "frequency": "hourly",
                "facets[parent][]": "PJM",
                "start": "2024-01-01",
                "end": "2024-01-01",
                "length": 5
            }
        },
        {
            "name": "Try daily-demand-forecast endpoint",
            "url": "https://api.eia.gov/v2/electricity/rto/daily-demand-forecast/data/",
            "params": {
                "api_key": api_key,
                "frequency": "daily",
                "data[0]": "value",
                "facets[respondent][]": "PJM",
                "start": "2024-01-01",
                "end": "2024-01-01",
                "length": 5
            }
        },
        {
            "name": "Try interchange endpoint",
            "url": "https://api.eia.gov/v2/electricity/rto/interchange-data/data/",
            "params": {
                "api_key": api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[fromba][]": "PJM",
                "start": "2024-01-01",
                "end": "2024-01-01",
                "length": 5
            }
        }
    ]
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Testing: {config['name']}")
        print(f"URL: {config['url']}")
        
        try:
            response = requests.get(config['url'], params=config['params'])
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Success! Response structure:")
                print(json.dumps(data, indent=2)[:1500])
                
                if 'response' in data and 'data' in data['response'] and data['response']['data']:
                    print(f"\nFound {len(data['response']['data'])} records")
                    print("First record:")
                    print(json.dumps(data['response']['data'][0], indent=2))
            else:
                print(f"Error response: {response.text[:500]}")
                
        except Exception as e:
            print(f"Exception: {e}")

    # Also let's check what endpoints are available
    print(f"\n{'='*60}")
    print("Checking available endpoints under /electricity/rto/")
    try:
        response = requests.get("https://api.eia.gov/v2/electricity/rto/", params={"api_key": api_key})
        if response.status_code == 200:
            data = response.json()
            print("Available routes:")
            if 'response' in data and 'routes' in data['response']:
                for route in data['response']['routes']:
                    print(f"  - {route['id']}: {route.get('name', 'No name')}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_eia_endpoints()