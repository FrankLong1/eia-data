#!/usr/bin/env python3
"""
Script to clean all raw EIA data files and save to cleaned folder.
"""

import os
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import logging
from data_cleaner import clean_eia_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_all_files():
    """Process all CSV files in the raw data directory."""
    
    # Define paths
    raw_dir = Path("data/raw")
    cleaned_dir = Path("data/cleaned")
    
    # Create cleaned directory if it doesn't exist
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all CSV files
    csv_files = list(raw_dir.rglob("*.csv"))
    
    if not csv_files:
        logging.error("No CSV files found in data/raw directory")
        return
    
    logging.info(f"Found {len(csv_files)} CSV files to process")
    
    # Process each file
    failed_files = []
    
    for csv_file in tqdm(csv_files, desc="Processing files"):
        try:
            # Read the raw data
            df = pd.read_csv(csv_file)
            
            # Get relative path from raw directory
            rel_path = csv_file.relative_to(raw_dir)
            
            # Create output path maintaining directory structure
            output_path = cleaned_dir / rel_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Map column names to expected format for cleaner
            # The raw data has: period, respondent, respondent-name, type, type-name, value, value-units
            # The cleaner expects: Timestamp, Balancing Authority, Demand, Adjusted demand (optional)
            
            # Rename columns to match cleaner expectations
            df_renamed = df.rename(columns={
                'period': 'Timestamp',
                'respondent': 'Balancing Authority',
                'value': 'Demand'
            })
            
            # Clean the data
            df_cleaned = clean_eia_data(
                df_renamed,
                datetime_col='Timestamp',
                demand_col_primary='Demand',
                adj_demand_col_name='Adjusted demand',  # Not present in raw data
                ba_col='Balancing Authority',
                perform_validation=False  # Turn off verbose logging for batch processing
            )
            
            # Save the cleaned data
            df_cleaned.to_csv(output_path, index=False)
            logging.info(f"Cleaned: {rel_path}")
            
        except Exception as e:
            logging.error(f"Failed to process {csv_file}: {str(e)}")
            failed_files.append(csv_file)
    
    # Summary
    logging.info(f"\nProcessing complete!")
    logging.info(f"Successfully processed: {len(csv_files) - len(failed_files)} files")
    
    if failed_files:
        logging.error(f"Failed to process {len(failed_files)} files:")
        for f in failed_files:
            logging.error(f"  - {f}")
    
    # Create a summary of what was cleaned
    summary_path = cleaned_dir / "cleaning_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("EIA Data Cleaning Summary\n")
        f.write("========================\n\n")
        f.write(f"Total files processed: {len(csv_files)}\n")
        f.write(f"Successfully cleaned: {len(csv_files) - len(failed_files)}\n")
        f.write(f"Failed: {len(failed_files)}\n\n")
        
        if failed_files:
            f.write("Failed files:\n")
            for failed in failed_files:
                f.write(f"  - {failed}\n")

if __name__ == "__main__":
    process_all_files()