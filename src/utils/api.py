"""
EIA API interaction utilities.

This module handles all API-related functionality including validation,
authentication, and request handling.
"""

import os
import requests
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# EIA API configuration
EIA_API_KEY = os.environ.get('EIA_API_KEY')
EIA_BASE_URL = "https://api.eia.gov/v2/"


def validate_api_key() -> bool:
    """
    Validate the EIA API key and ensure it's properly configured.
    
    Provides helpful error messages if the API key is missing or invalid.
    
    Returns:
        bool: True if API key is valid and working, False otherwise
    """
    if not EIA_API_KEY:
        logging.error("EIA_API_KEY not found in environment")
        print("Error: EIA_API_KEY not found in environment")
        print("Please set your API key in the .env file")
        print("\nTo get an API key:")
        print("1. Visit https://www.eia.gov/opendata/register.php")
        print("2. Register for a free API key")
        print("3. Create a .env file in the project root")
        print("4. Add: EIA_API_KEY=your_key_here")
        return False
    
    if not check_api_key():
        logging.error("API key validation failed")
        print("Error: API key validation failed")
        print("Please check your API key is correct")
        return False
        
    return True


def check_api_key() -> bool:
    """
    Test the API key by making a simple request to the EIA API.
    
    Returns:
        bool: True if API key is valid, False otherwise
    """
    test_url = f"{EIA_BASE_URL}electricity/retail-sales/data/"
    test_params = {
        'api_key': EIA_API_KEY,
        'frequency': 'annual',
        'data[0]': 'sales',
        'start': '2023',
        'end': '2023',
        'length': 1
    }
    
    try:
        response = requests.get(test_url, params=test_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'response' in data:
            logging.info("API key is valid!")
            return True
        else:
            logging.error("API key may be invalid or API structure has changed")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking API key: {e}")
        return False


def make_eia_request(endpoint: str, params: Dict, timeout: int = 30) -> Optional[Dict]:
    """
    Make a request to the EIA API with error handling.
    
    This function handles common API errors and provides consistent
    error logging across all API calls.
    
    Args:
        endpoint: API endpoint (relative to base URL)
        params: Query parameters for the request
        timeout: Request timeout in seconds (default: 30)
        
    Returns:
        Response data as dictionary, or None if request failed
    """
    url = f"{EIA_BASE_URL}{endpoint}"
    
    # Always add API key
    params['api_key'] = EIA_API_KEY
    
    try:
        response = requests.get(url, params=params, timeout=timeout)
        
        if response.status_code != 200:
            logging.error(f"HTTP {response.status_code}: {response.text[:200]}")
            return None
            
        return response.json()
        
    except requests.exceptions.Timeout:
        logging.error(f"Request timeout after {timeout} seconds")
        return None
        
    except requests.exceptions.ConnectionError:
        logging.error("Connection error - check your internet connection")
        return None
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return None
        
    except ValueError as e:
        logging.error(f"Invalid JSON response: {e}")
        return None