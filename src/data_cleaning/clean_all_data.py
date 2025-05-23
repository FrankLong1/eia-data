#!/usr/bin/env python3
"""
Script to clean all downloaded EIA data files.
"""

import os
from pathlib import Path
import logging
from data_cleaner import clean_eia_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_all_data():
    """Clean all downloaded EIA data files."""
    
    raw_dir = Path("data/raw")
    cleaned_dir = Path("data/cleaned")
    
    if not raw_dir.exists():
        logging.error("Raw data directory not found")
        return
    
    # Create cleaned directory if it doesn't exist
    cleaned_dir.mkdir(exist_ok=True)
    
    # Process each BA folder
    for ba_dir in raw_dir.iterdir():
        if not ba_dir.is_dir() or ba_dir.name == "backup_old_structure":
            continue
            
        logging.info(f"Processing BA directory: {ba_dir.name}")
        
        # Create corresponding BA directory in cleaned folder
        ba_cleaned_dir = cleaned_dir / ba_dir.name
        ba_cleaned_dir.mkdir(exist_ok=True)
        
        # Process each CSV file in the BA directory
        for file in ba_dir.glob("*.csv"):
            try:
                logging.info(f"Cleaning file: {file.name}")
                
                # Clean the data
                cleaned_df = clean_eia_data(
                    str(file),
                    ba_col='Balancing Authority'
                )
                
                # Save cleaned data
                output_file = ba_cleaned_dir / f"cleaned_{file.name}"
                cleaned_df.to_csv(output_file, index=False)
                logging.info(f"Saved cleaned data to: {output_file}")
                
            except Exception as e:
                logging.error(f"Error processing {file}: {str(e)}")
                continue
    
    logging.info("Data cleaning complete!")

if __name__ == "__main__":
    clean_all_data()