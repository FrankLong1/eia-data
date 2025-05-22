import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Test if we can access EIA API with key
def test_eia_api():
    """Test various EIA API endpoints"""
    
    api_key = os.environ.get('EIA_API_KEY')
    
    # Try different API endpoints
    endpoints = [
        # Try v2 API endpoints
        {
            "url": "https://api.eia.gov/v2/electricity/rto/hourly-demand/data/",
            "params": {
                "api_key": api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[respondent][]": "PJM",
                "start": "2024-01-01T00",
                "end": "2024-01-02T00",
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "length": 5
            }
        },
        # Try simpler endpoint
        {
            "url": "https://api.eia.gov/v2/electricity/rto/hourly-demand/data/",
            "params": {
                "api_key": api_key,
                "respondent": "PJM",
                "start": "2024-01-01",
                "end": "2024-01-01",
                "length": 5
            }
        },
        # Try v1 API format
        {
            "url": "https://api.eia.gov/series/",
            "params": {
                "api_key": api_key,
                "series_id": "EBA.PJM-ALL.D.H"
            }
        }
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting: {endpoint['url']}")
        print(f"Params: {endpoint['params']}")
        try:
            response = requests.get(endpoint['url'], params=endpoint['params'])
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Response structure:")
                print(json.dumps(data, indent=2)[:1000] + "...")
            else:
                print(f"Response: {response.text[:500]}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_eia_api()