"""
Data formatting and parsing utilities.

This module contains functions for formatting dates, parsing filenames,
and other data presentation utilities.
"""

from typing import Dict, Optional
from datetime import datetime
import re


def format_date_range(start_date: str, end_date: str) -> str:
    """
    Format a date range for display.
    
    Args:
        start_date: Start date in YYYY-MM or YYYY-MM-DD format
        end_date: End date in YYYY-MM or YYYY-MM-DD format
        
    Returns:
        Formatted date range string
        
    Examples:
        >>> format_date_range('2023-01', '2023-12')
        'Jan - Dec 2023'
        >>> format_date_range('2023-01', '2024-03')
        'Jan 2023 - Mar 2024'
    """
    try:
        # Try parsing as YYYY-MM first
        try:
            start = datetime.strptime(start_date, '%Y-%m')
            end = datetime.strptime(end_date, '%Y-%m')
            date_format = '%b %Y'
        except ValueError:
            # Try YYYY-MM-DD
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            date_format = '%b %d, %Y'
        
        if start.year == end.year:
            if date_format == '%b %Y':
                return f"{start.strftime('%b')} - {end.strftime('%b %Y')}"
            else:
                return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
        else:
            return f"{start.strftime(date_format)} - {end.strftime(date_format)}"
            
    except ValueError:
        return f"{start_date} to {end_date}"


def parse_plant_filename(filename: str) -> Dict[str, str]:
    """
    Parse plant data filename to extract metadata.
    
    Args:
        filename: Filename like "3470_generation_2023-01_2023-12.csv"
        
    Returns:
        Dictionary with plant_id, data_type, start_date, end_date
        
    Example:
        >>> parse_plant_filename("3470_generation_2023-01_2023-12.csv")
        {'plant_id': '3470', 'data_type': 'generation', 
         'start_date': '2023-01', 'end_date': '2023-12'}
    """
    # Remove .csv extension if present
    if filename.endswith('.csv'):
        filename = filename[:-4]
    
    parts = filename.split('_')
    
    if len(parts) >= 4:
        return {
            'plant_id': parts[0],
            'data_type': parts[1],
            'start_date': parts[2],
            'end_date': parts[3]
        }
    else:
        return {
            'plant_id': parts[0] if len(parts) > 0 else 'unknown',
            'data_type': parts[1] if len(parts) > 1 else 'unknown',
            'start_date': 'unknown',
            'end_date': 'unknown'
        }


def format_number_with_commas(number: float, decimals: int = 0) -> str:
    """
    Format a number with thousands separators.
    
    Args:
        number: Number to format
        decimals: Number of decimal places (default: 0)
        
    Returns:
        Formatted string with commas
        
    Examples:
        >>> format_number_with_commas(1234567)
        '1,234,567'
        >>> format_number_with_commas(1234567.89, 2)
        '1,234,567.89'
    """
    if decimals > 0:
        return f"{number:,.{decimals}f}"
    else:
        return f"{int(number):,}"


def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    Parse various date string formats into datetime objects.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object or None if parsing fails
        
    Supports formats:
        - YYYY-MM-DD
        - YYYY-MM
        - YYYY-MM-DDTHH
        - YYYY-MM-DD HH:MM:SS
    """
    formats = [
        '%Y-%m-%d',
        '%Y-%m',
        '%Y-%m-%dT%H',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d',
        '%m/%d/%Y'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    return None


def format_mwh_to_gwh(mwh: float, decimals: int = 1) -> str:
    """
    Convert megawatt-hours to gigawatt-hours with formatting.
    
    Args:
        mwh: Value in megawatt-hours
        decimals: Number of decimal places
        
    Returns:
        Formatted string with GWh unit
        
    Example:
        >>> format_mwh_to_gwh(1234567)
        '1,234.6 GWh'
    """
    gwh = mwh / 1000
    return f"{gwh:,.{decimals}f} GWh"


def format_mwh_to_twh(mwh: float, decimals: int = 2) -> str:
    """
    Convert megawatt-hours to terawatt-hours with formatting.
    
    Args:
        mwh: Value in megawatt-hours
        decimals: Number of decimal places
        
    Returns:
        Formatted string with TWh unit
        
    Example:
        >>> format_mwh_to_twh(1234567890)
        '1.23 TWh'
    """
    twh = mwh / 1_000_000
    return f"{twh:,.{decimals}f} TWh"


def clean_plant_name(name: str) -> str:
    """
    Clean and standardize plant names.
    
    Args:
        name: Raw plant name
        
    Returns:
        Cleaned plant name
        
    Example:
        >>> clean_plant_name("W.A. PARISH")
        'W.A. Parish'
    """
    # Handle all caps
    if name.isupper():
        # Convert to title case but preserve certain patterns
        name = name.title()
        # Fix common patterns
        name = re.sub(r'\b([A-Z])\.([A-Z])\b', r'\1.\2', name)  # Fix initials
        
    # Remove extra spaces
    name = ' '.join(name.split())
    
    return name