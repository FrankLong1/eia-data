import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_region_data():
    """Test the region-data endpoint"""
    
    api_key = os.environ.get('EIA_API_KEY')
    
    # Test the region-data endpoint
    url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    
    params = {
        "api_key": api_key,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "PJM",
        "start": "2024-01-01T00",
        "end": "2024-01-01T05",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 50
    }
    
    print(f"Testing: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")
    
    try:
        response = requests.get(url, params=params)
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nSuccess! Response structure:")
            print(json.dumps(data, indent=2))
            
            if 'response' in data and 'data' in data['response'] and data['response']['data']:
                print(f"\nFound {len(data['response']['data'])} records")
                
                # Show data structure
                for i, record in enumerate(data['response']['data'][:3]):
                    print(f"\nRecord {i+1}:")
                    print(json.dumps(record, indent=2))
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_region_data()