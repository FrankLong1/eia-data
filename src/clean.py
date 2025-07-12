#!/usr/bin/env python3
"""
Simplified data cleaning module for EIA curtailment analysis.

This module provides core functionality for cleaning BA aggregate data including:
- IQR-based outlier detection and removal
- Linear interpolation for missing values
- Timezone normalization to local time
- BA label standardization
- Peak demand validation

Focus: BA aggregate data cleaning for curtailment analysis only.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Union, Dict
import config


def normalize_datetime(df: pd.DataFrame, datetime_col: str = 'Timestamp') -> pd.DataFrame:
    """Convert datetime column to pandas datetime format."""
    if datetime_col not in df.columns:
        return df
    
    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors='coerce')
    return df




def interpolate_nan_values(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Fill all NaN values using linear interpolation.
    
    Handles NaN values from multiple sources:
    - Original missing data from EIA API
    - Zeros (replaced with NaN - not plausible that a BA has zero demand)
    - Outliers marked as NaN by detect_outliers()
    """
    df = df.copy()
    
    for col in columns:
        if col not in df.columns:
            continue
        
        # Replace zeros with NaN (BA can't have zero demand)
        df[col] = df[col].replace(0, np.nan)
        
        # Interpolate all NaN values
        df[col] = df[col].interpolate(method='linear', limit_direction='both')
    
    return df


def detect_outliers(df: pd.DataFrame, demand_col: str = 'Demand') -> pd.DataFrame:
    """
    Detect outliers using simple percentile-based bounds and replace with NaN.
    
    Too low: < 0.5 * 10th percentile (catches weird low values)
    Too high: > min(200 GW, 2x 90th percentile) (catches physically impossible or statistically weird peaks)
    """
    if demand_col not in df.columns:
        return df
    
    df = df.copy()
    
    # Need sufficient data for statistical analysis
    clean_series = df[demand_col].dropna()
    if len(clean_series) < 10:
        return df
    
    # Simple percentile-based bounds
    p10 = clean_series.quantile(0.10)
    p90 = clean_series.quantile(0.90)
    
    # Too low: half the 10th percentile (catches weird low values)
    lower_bound = 0.5 * p10
    
    # Too high: minimum of 200 GW or 2x 90th percentile
    upper_bound = min(200000, 2.0 * p90)
    
    # Find outliers
    too_low = df[demand_col] < lower_bound
    too_high = df[demand_col] > upper_bound
    outliers = too_low | too_high
    
    if outliers.sum() > 0:
        logging.info(f"Marking {outliers.sum()} outliers as NaN: "
                    f"{too_low.sum()} too low, {too_high.sum()} too high")
        
        # Replace outliers with NaN
        df.loc[outliers, demand_col] = np.nan
    
    return df


def clean_file(input_path: Union[str, Path]) -> pd.DataFrame:
    """Clean a single BA aggregate data file."""
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    logging.info(f"Cleaning file: {input_path}")
    
    # Load data
    df = pd.read_csv(input_path)
    
    # Rename columns to standard format
    column_mapping = {
        'period': 'Timestamp',
        'value': 'Demand',
        'respondent-name': 'Balancing Authority'
    }
    df = df.rename(columns=column_mapping)
    
    # Clean data pipeline
    df = normalize_datetime(df)
    
    if 'Demand' not in df.columns or df['Demand'].isna().all():
        logging.error("No demand data found in file")
        return df
    
    df = detect_outliers(df)
    df = interpolate_nan_values(df, ['Demand'])
    
    return df


def clean_data_directory(input_dir: Union[str, Path], output_dir: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """Clean all CSV files in a directory and save them."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for file_path in input_dir.glob("**/*.csv"):
        try:
            # Clean file (returns DataFrame only)
            df_cleaned = clean_file(file_path)
            
            # Save cleaned data
            output_file = output_dir / f"cleaned_{file_path.name}"
            df_cleaned.to_csv(output_file, index=False)
            logging.info(f"Saved cleaned data to: {output_file}")
            
            results[file_path.name] = df_cleaned
            
        except Exception as e:
            logging.error(f"Error cleaning {file_path}: {e}")
            continue
    
    logging.info(f"Cleaned {len(results)} files from {input_dir}")
    return results


if __name__ == "__main__":
    clean_data_directory("data/raw", "data/cleaned")