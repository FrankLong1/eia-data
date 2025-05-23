#!/usr/bin/env python3
"""
Script to clean all downloaded EIA data files.
"""

import os
from pathlib import Path
import logging
import pandas as pd
from DataCleaner import clean_eia_data

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
                
                # Read the raw data
                df = pd.read_csv(file)
                
                # Rename columns to match expected format
                df_renamed = df.rename(columns={
                    'period': 'Timestamp',
                    'value': 'Demand',
                    'respondent-name': 'Balancing Authority'
                })
                
                # Check if there's an adjusted demand column (type-name might indicate this)
                if 'type-name' in df.columns and 'demand (adjusted)' in df['type-name'].values:
                    # Create separate columns for regular and adjusted demand
                    demand_mask = df['type-name'] == 'demand'
                    adj_mask = df['type-name'] == 'demand (adjusted)'
                    
                    if demand_mask.any():
                        df_renamed.loc[demand_mask, 'Demand'] = df.loc[demand_mask, 'value']
                    if adj_mask.any():
                        df_renamed['Adjusted demand'] = None
                        df_renamed.loc[adj_mask, 'Adjusted demand'] = df.loc[adj_mask, 'value']
                
                # Clean the data
                df_cleaned = clean_eia_data(
                    df_renamed,
                    datetime_col='Timestamp',
                    demand_col_primary='Demand',
                    adj_demand_col_name='Adjusted demand',
                    ba_col='Balancing Authority'
                )
                
                # Save cleaned data
                output_file = ba_cleaned_dir / f"cleaned_{file.name}"
                df_cleaned.to_csv(output_file, index=False)
                logging.info(f"Saved cleaned data to: {output_file}")
                
            except Exception as e:
                logging.error(f"Error processing {file}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
    
    logging.info("Data cleaning complete!")

if __name__ == "__main__":
    clean_all_data()