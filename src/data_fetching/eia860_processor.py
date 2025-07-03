"""
EIA-860 Data Processor

Handles downloading and processing of EIA-860 dataset files for plant location 
and ownership information. This module was extracted from download_plant_data.py
to improve code organization and maintainability.
"""

import os
import logging
import zipfile
import requests
import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PlantLocationData:
    """Data class for plant location and ownership information."""
    plant_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    county: Optional[str] = None
    zip_code: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    balancing_authority_code_eia: Optional[str] = None
    balancing_authority_name_eia: Optional[str] = None
    nerc_region: Optional[str] = None
    primary_purpose: Optional[str] = None
    owners: Optional[List[Dict[str, Optional[str]]]] = None


class EIA860Processor:
    """
    Processor for EIA-860 dataset files.
    
    The EIA-860 dataset contains detailed plant-level information including:
    - Geographic coordinates (latitude/longitude)
    - Balancing authority assignments
    - Ownership information
    - Operational details
    
    This processor handles downloading, caching, and parsing the Excel files
    from the EIA-860 annual releases.
    """
    
    def __init__(self, download_dir: str = 'plant_data/eia860_downloads'):
        """
        Initialize the EIA-860 processor.
        
        Args:
            download_dir: Directory for caching downloaded files
        """
        self.download_dir = download_dir
        self.url_pattern = "https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"
        
        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)
    
    def get_plant_data(self, year: int = 2023) -> Dict[str, PlantLocationData]:
        """
        Get complete plant location and ownership data for a given year.
        
        Args:
            year: Year of EIA-860 data to download
            
        Returns:
            Dictionary mapping plant IDs to PlantLocationData objects
            
        Raises:
            requests.RequestException: If download fails
            ValueError: If required files are not found in the zip
        """
        logger.info(f"Processing EIA-860 data for year {year}")
        
        # Download and cache the zip file
        zip_path = self._download_zip_file(year)
        
        # Process the zip file contents
        with zipfile.ZipFile(zip_path) as zipf:
            plant_data = self._process_zip_contents(zipf)
        
        logger.info(f"Successfully processed EIA-860 data for {len(plant_data)} plants")
        return plant_data
    
    def _download_zip_file(self, year: int) -> str:
        """
        Download EIA-860 zip file for the given year, using cache if available.
        
        Args:
            year: Year of data to download
            
        Returns:
            Path to the downloaded zip file
            
        Raises:
            requests.RequestException: If download fails
        """
        zip_path = os.path.join(self.download_dir, f'eia860_{year}.zip')
        
        # Use cached file if it exists
        if os.path.exists(zip_path):
            logger.info(f"Using cached EIA-860 zip from {zip_path}")
            return zip_path
        
        # Download the file
        logger.info(f"Downloading EIA-860 data for year {year}")
        url = self.url_pattern.format(year=year)
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
                
            logger.info(f"Saved EIA-860 zip to {zip_path}")
            return zip_path
            
        except requests.RequestException as e:
            logger.error(f"Failed to download EIA-860 data: {e}")
            raise
    
    def _process_zip_contents(self, zipf: zipfile.ZipFile) -> Dict[str, PlantLocationData]:
        """
        Process the contents of an EIA-860 zip file.
        
        Args:
            zipf: Open zipfile object
            
        Returns:
            Dictionary of plant data
            
        Raises:
            ValueError: If required files are not found
        """
        # Find the relevant Excel files in the zip
        file_list = zipf.namelist()
        
        plant_file = self._find_file_by_pattern(file_list, '2___Plant', '.xlsx')
        owner_file = self._find_file_by_pattern(file_list, '4___Owner', '.xlsx')
        
        if not plant_file:
            raise ValueError("Plant file (2___Plant*.xlsx) not found in EIA-860 zip")
        
        # Parse plant location data (required)
        plant_data = self._parse_plant_file(zipf, plant_file)
        
        # Parse ownership data (optional)
        if owner_file:
            self._parse_owner_file(zipf, owner_file, plant_data)
        else:
            logger.warning("Owner file not found - continuing without ownership data")
        
        return plant_data
    
    def _find_file_by_pattern(self, file_list: List[str], pattern: str, extension: str) -> Optional[str]:
        """
        Find a file in the zip that matches the given pattern and extension.
        
        Args:
            file_list: List of files in the zip
            pattern: Pattern to search for in filename
            extension: File extension to match
            
        Returns:
            Matching filename, or None if not found
        """
        for filename in file_list:
            if pattern in filename and filename.endswith(extension):
                return filename
        return None
    
    def _parse_plant_file(self, zipf: zipfile.ZipFile, plant_file: str) -> Dict[str, PlantLocationData]:
        """
        Parse plant location data from the EIA-860 plant file.
        
        Args:
            zipf: Open zipfile object
            plant_file: Name of the plant Excel file
            
        Returns:
            Dictionary mapping plant IDs to PlantLocationData objects
            
        Raises:
            ValueError: If plant ID column is not found
        """
        logger.info(f"Reading plant data from {plant_file}")
        
        try:
            with zipf.open(plant_file) as f:
                # Skip the first row which is usually a header
                df = pd.read_excel(f, engine='openpyxl', skiprows=1)
        except Exception as e:
            logger.error(f"Failed to read plant file {plant_file}: {e}")
            raise ValueError(f"Could not read plant file: {e}")
        
        # Find the plant ID column
        plant_id_col = self._find_plant_id_column(df.columns)
        if not plant_id_col:
            available_cols = list(df.columns)[:10]  # Show first 10 columns
            raise ValueError(f"Plant ID column not found. Available columns: {available_cols}")
        
        # Process each plant record
        plant_data = {}
        for _, row in df.iterrows():
            plant_id = str(row.get(plant_id_col, ''))
            if not plant_id or plant_id == 'nan':
                continue
            
            plant_data[plant_id] = PlantLocationData(
                plant_id=plant_id,
                latitude=self._safe_float(row.get('Latitude')),
                longitude=self._safe_float(row.get('Longitude')),
                county=self._safe_str(row.get('County')),
                zip_code=self._safe_str(row.get('Zip') or row.get('Zip Code')),
                street_address=self._safe_str(row.get('Street Address')),
                city=self._safe_str(row.get('City')),
                balancing_authority_code_eia=self._safe_str(row.get('Balancing Authority Code')),
                balancing_authority_name_eia=self._safe_str(row.get('Balancing Authority Name')),
                nerc_region=self._safe_str(row.get('NERC Region')),
                primary_purpose=self._safe_str(row.get('Primary Purpose NAICS Code'))
            )
        
        logger.info(f"Parsed location data for {len(plant_data)} plants")
        return plant_data
    
    def _parse_owner_file(self, zipf: zipfile.ZipFile, owner_file: str, 
                         plant_data: Dict[str, PlantLocationData]) -> None:
        """
        Parse ownership data and add it to existing plant data.
        
        Args:
            zipf: Open zipfile object
            owner_file: Name of the owner Excel file
            plant_data: Existing plant data dictionary to update
        """
        logger.info(f"Reading ownership data from {owner_file}")
        
        try:
            with zipf.open(owner_file) as f:
                df = pd.read_excel(f, engine='openpyxl', skiprows=1)
        except Exception as e:
            logger.warning(f"Failed to read owner file {owner_file}: {e}")
            return
        
        # Find plant ID column
        plant_id_col = self._find_plant_id_column(df.columns)
        if not plant_id_col:
            logger.warning(f"Plant ID column not found in {owner_file}")
            return
        
        # Process ownership records
        for _, row in df.iterrows():
            plant_id = str(row.get(plant_id_col, ''))
            if not plant_id or plant_id == 'nan' or plant_id not in plant_data:
                continue
            
            # Initialize owners list if not exists
            if plant_data[plant_id].owners is None:
                plant_data[plant_id].owners = []
            
            owner_name = self._safe_str(row.get('Owner Name'))
            percent_owned = self._safe_float(row.get('Percent Owned'))
            
            if owner_name:
                plant_data[plant_id].owners.append({
                    'name': owner_name,
                    'percent_owned': str(percent_owned) if percent_owned is not None else None
                })
        
        # Count plants with ownership data
        plants_with_owners = sum(1 for p in plant_data.values() if p.owners)
        logger.info(f"Added ownership data for {plants_with_owners} plants")
    
    def _find_plant_id_column(self, columns) -> Optional[str]:
        """
        Find the plant ID column from a list of column names.
        
        Args:
            columns: DataFrame columns or list of column names
            
        Returns:
            Plant ID column name, or None if not found
        """
        possible_names = ['Plant Code', 'Plant ID', 'PlantCode', 'PlantID']
        for col_name in possible_names:
            if col_name in columns:
                return col_name
        return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float, returning None for invalid values."""
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_str(self, value) -> Optional[str]:
        """Safely convert value to string, returning None for null/empty values."""
        if pd.isna(value) or value == '':
            return None
        return str(value)
    
    def to_dataframe(self, plant_data: Dict[str, PlantLocationData]) -> pd.DataFrame:
        """
        Convert plant data dictionary to a pandas DataFrame.
        
        Args:
            plant_data: Dictionary of PlantLocationData objects
            
        Returns:
            DataFrame with plant information
        """
        records = []
        
        for plant_id, data in plant_data.items():
            record = {
                'plant_id': plant_id,
                'latitude': data.latitude,
                'longitude': data.longitude,
                'county': data.county,
                'zip_code': data.zip_code,
                'street_address': data.street_address,
                'city': data.city,
                'balancing_authority_code_eia': data.balancing_authority_code_eia,
                'balancing_authority_name_eia': data.balancing_authority_name_eia,
                'nerc_region': data.nerc_region,
                'primary_purpose': data.primary_purpose
            }
            
            # Handle ownership data
            if data.owners:
                owner_strings = [
                    f"{owner['name']} ({owner['percent_owned']}%)" 
                    for owner in data.owners 
                    if owner.get('name')
                ]
                record['owners'] = '; '.join(owner_strings)
            else:
                record['owners'] = None
            
            # Create lat/lng tuple for convenience
            if data.latitude is not None and data.longitude is not None:
                record['lat_lng_tuple'] = f"({data.latitude}, {data.longitude})"
            else:
                record['lat_lng_tuple'] = None
            
            records.append(record)
        
        return pd.DataFrame(records)


# Convenience function for backward compatibility
def fetch_eia860_location_ownership_data(year: int = 2023) -> Dict[str, dict]:
    """
    Fetch EIA-860 data using the improved processor.
    
    This function maintains backward compatibility with the original implementation
    while using the new, more maintainable EIA860Processor class.
    
    Args:
        year: Year of EIA-860 data to download
        
    Returns:
        Dictionary mapping plant IDs to location/ownership data (legacy format)
    """
    processor = EIA860Processor()
    plant_data = processor.get_plant_data(year)
    
    # Convert to legacy dictionary format for backward compatibility
    legacy_data = {}
    for plant_id, data in plant_data.items():
        legacy_data[plant_id] = {
            'latitude': data.latitude,
            'longitude': data.longitude,
            'county': data.county,
            'zip_code': data.zip_code,
            'street_address': data.street_address,
            'city': data.city,
            'balancing_authority_code_eia': data.balancing_authority_code_eia,
            'balancing_authority_name_eia': data.balancing_authority_name_eia,
            'nerc_region': data.nerc_region,
            'primary_purpose': data.primary_purpose,
            'owners': data.owners or []
        }
    
    return legacy_data