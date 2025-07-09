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
from typing import List, Optional, Dict, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# BA label mappings from research paper
BA_MAPPING = {
    "CPLE": "DEP",    # Duke Energy Progress East
    "DUK": "DEC",     # Duke Energy Carolinas
    "SC": "SCP",      # Santee Cooper
    "SWPP": "SPP",    # Southwest Power Pool
    "SCEG": "DESC",   # Dominion Energy South Carolina
    "FPC": "DEF",     # Duke Energy Florida
    "CISO": "CAISO",  # California ISO
    "BPAT": "BPA",    # Bonneville Power Administration
    "NYIS": "NYISO",  # New York ISO
    "ERCO": "ERCOT",  # Texas
    "ISNE": "ISO-NE"  # New England
}


def normalize_datetime(df: pd.DataFrame, datetime_col: str = 'Timestamp') -> pd.DataFrame:
    """
    Convert datetime column to pandas datetime format with timezone handling.
    
    Args:
        df: DataFrame with datetime column
        datetime_col: Name of datetime column
        
    Returns:
        DataFrame with normalized datetime column
    """
    if datetime_col not in df.columns:
        logging.warning(f"Datetime column '{datetime_col}' not found")
        return df
    
    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors='coerce')
    
    # Log conversion stats
    null_count = df[datetime_col].isna().sum()
    if null_count > 0:
        logging.warning(f"Failed to parse {null_count} datetime values")
    
    return df


def standardize_ba_labels(df: pd.DataFrame, ba_col: str = 'Balancing Authority') -> pd.DataFrame:
    """
    Standardize BA codes to research paper naming convention.
    
    Args:
        df: DataFrame with BA column
        ba_col: Name of BA column
        
    Returns:
        DataFrame with standardized BA labels
    """
    if ba_col not in df.columns:
        logging.warning(f"BA column '{ba_col}' not found")
        return df
    
    df = df.copy()
    original_values = df[ba_col].unique()
    df[ba_col] = df[ba_col].map(BA_MAPPING).fillna(df[ba_col])
    
    # Log mapping results
    mapped_values = df[ba_col].unique()
    mapped_count = len(set(original_values) & set(BA_MAPPING.keys()))
    logging.info(f"Mapped {mapped_count} BA codes to standard names")
    
    return df


def create_unified_demand(df: pd.DataFrame, 
                         demand_col: str = 'Demand',
                         adj_demand_col: str = 'Adjusted demand') -> pd.DataFrame:
    """
    Create unified demand column, preferring adjusted values when available.
    
    Args:
        df: DataFrame with demand columns
        demand_col: Primary demand column name
        adj_demand_col: Adjusted demand column name
        
    Returns:
        DataFrame with 'Unified Demand' column
    """
    df = df.copy()
    
    # Create unified demand column
    if adj_demand_col in df.columns and demand_col in df.columns:
        df['Unified Demand'] = df[adj_demand_col].fillna(df[demand_col])
        logging.info("Created Unified Demand using adjusted and primary values")
    elif adj_demand_col in df.columns:
        df['Unified Demand'] = df[adj_demand_col]
        logging.info("Created Unified Demand using adjusted values only")
    elif demand_col in df.columns:
        df['Unified Demand'] = df[demand_col]
        logging.info("Created Unified Demand using primary values only")
    else:
        df['Unified Demand'] = np.nan
        logging.warning("No demand columns found, created empty Unified Demand")
    
    return df


def interpolate_missing_values(df: pd.DataFrame, 
                              columns: List[str],
                              method: str = 'linear') -> pd.DataFrame:
    """
    Fill missing values and zeros using linear interpolation.
    
    Args:
        df: DataFrame to interpolate
        columns: List of columns to interpolate
        method: Interpolation method ('linear', 'time', etc.)
        
    Returns:
        DataFrame with interpolated values
    """
    df = df.copy()
    
    for col in columns:
        if col not in df.columns:
            logging.warning(f"Column '{col}' not found for interpolation")
            continue
        
        # Track initial missing values
        initial_missing = df[col].isna().sum()
        initial_zeros = (df[col] == 0).sum()
        
        # Replace zeros with NaN, then interpolate
        df[col] = df[col].replace(0, np.nan)
        df[col] = df[col].interpolate(method=method, limit_direction='both')
        
        # Log interpolation results
        final_missing = df[col].isna().sum()
        filled_count = (initial_missing + initial_zeros) - final_missing
        logging.info(f"Filled {filled_count} missing/zero values in {col}")
    
    return df


def remove_outliers_iqr(df: pd.DataFrame, 
                       demand_col: str = 'Unified Demand',
                       ba_col: Optional[str] = None,
                       iqr_factor: float = 3.0) -> pd.DataFrame:
    """
    Remove outliers using IQR method as described in the research paper.
    
    Args:
        df: DataFrame with demand data
        demand_col: Name of demand column
        ba_col: Name of BA column (for per-BA outlier detection)
        iqr_factor: IQR multiplier for outlier threshold
        
    Returns:
        DataFrame with outliers removed and interpolated
    """
    if demand_col not in df.columns:
        logging.warning(f"Demand column '{demand_col}' not found")
        return df
    
    df = df.copy()
    
    def detect_outliers(series: pd.Series) -> pd.Series:
        """Detect outliers using IQR method."""
        clean_series = series.dropna()
        
        if len(clean_series) < 10:
            return pd.Series(False, index=series.index)
        
        # Calculate IQR on clean data
        Q1 = clean_series.quantile(0.25)
        Q3 = clean_series.quantile(0.75)
        IQR = Q3 - Q1
        
        # Define outlier bounds
        lower_bound = Q1 - iqr_factor * IQR
        upper_bound = Q3 + iqr_factor * IQR
        
        # Additional sanity check: no single BA should exceed 200 GW
        upper_bound = min(upper_bound, 200000)
        
        return (series < lower_bound) | (series > upper_bound)
    
    # Apply outlier detection
    if ba_col and ba_col in df.columns:
        # Detect outliers within each BA
        outlier_mask = pd.Series(False, index=df.index)
        
        for ba in df[ba_col].unique():
            ba_mask = df[ba_col] == ba
            ba_data = df.loc[ba_mask, demand_col]
            
            ba_outliers = detect_outliers(ba_data)
            outlier_mask.loc[ba_mask] = ba_outliers
            
            if ba_outliers.sum() > 0:
                logging.info(f"BA {ba}: Found {ba_outliers.sum()} outliers using IQR method")
    else:
        # Global outlier detection
        outlier_mask = detect_outliers(df[demand_col])
    
    # Remove outliers and interpolate
    outlier_count = outlier_mask.sum()
    if outlier_count > 0:
        logging.info(f"Removing {outlier_count} outliers using IQR method")
        
        # Replace outliers with NaN
        df.loc[outlier_mask, demand_col] = np.nan
        
        # Interpolate within each BA if possible
        if ba_col and ba_col in df.columns:
            for ba in df[ba_col].unique():
                ba_mask = df[ba_col] == ba
                df.loc[ba_mask, demand_col] = df.loc[ba_mask, demand_col].interpolate(
                    method='linear', limit_direction='both'
                )
        else:
            df[demand_col] = df[demand_col].interpolate(method='linear', limit_direction='both')
    
    return df


def validate_peak_demand(df: pd.DataFrame,
                        demand_col: str = 'Unified Demand',
                        ba_col: Optional[str] = None,
                        peak_threshold: float = 2.0) -> pd.DataFrame:
    """
    Validate and correct unrealistic peak demands.
    
    Args:
        df: DataFrame with demand data
        demand_col: Name of demand column
        ba_col: Name of BA column
        peak_threshold: Multiple of historical max for peak validation
        
    Returns:
        DataFrame with validated peak demands
    """
    if demand_col not in df.columns:
        logging.warning(f"Demand column '{demand_col}' not found")
        return df
    
    df = df.copy()
    
    if ba_col and ba_col in df.columns:
        # Validate peaks within each BA
        for ba in df[ba_col].unique():
            ba_mask = df[ba_col] == ba
            ba_data = df.loc[ba_mask, demand_col]
            
            # Calculate threshold based on 90th percentile (more robust than max)
            p90 = ba_data.quantile(0.90)
            threshold = p90 * peak_threshold
            
            # Flag extreme peaks
            extreme_peaks = ba_data > threshold
            if extreme_peaks.sum() > 0:
                logging.info(f"BA {ba}: Found {extreme_peaks.sum()} extreme peaks")
                
                # Replace with interpolated values
                df.loc[ba_mask & extreme_peaks, demand_col] = np.nan
                df.loc[ba_mask, demand_col] = df.loc[ba_mask, demand_col].interpolate(
                    method='linear', limit_direction='both'
                )
    
    return df


def clean_ba_data(df: pd.DataFrame,
                  datetime_col: str = 'Timestamp',
                  demand_col: str = 'Demand',
                  adj_demand_col: str = 'Adjusted demand',
                  ba_col: str = 'Balancing Authority',
                  iqr_factor: float = 3.0,
                  peak_threshold: float = 2.0) -> pd.DataFrame:
    """
    Complete cleaning pipeline for BA aggregate data.
    
    Implementation of cleaning methods from the research paper:
    1. Normalize datetime to local time
    2. Standardize BA labels
    3. Create unified demand column
    4. Remove outliers using IQR method
    5. Interpolate missing values
    6. Validate peak demands
    
    Args:
        df: Raw BA aggregate data
        datetime_col: Datetime column name
        demand_col: Primary demand column name
        adj_demand_col: Adjusted demand column name
        ba_col: Balancing authority column name
        iqr_factor: IQR multiplier for outlier detection
        peak_threshold: Peak validation threshold
        
    Returns:
        Cleaned DataFrame ready for curtailment analysis
    """
    logging.info("Starting BA data cleaning pipeline")
    
    # Step 1: Normalize datetime
    df = normalize_datetime(df, datetime_col)
    
    # Step 2: Standardize BA labels
    df = standardize_ba_labels(df, ba_col)
    
    # Step 3: Create unified demand column
    df = create_unified_demand(df, demand_col, adj_demand_col)
    
    if 'Unified Demand' not in df.columns or df['Unified Demand'].isna().all():
        logging.error("Failed to create unified demand column")
        return df
    
    # Step 4: Remove outliers using IQR method
    df = remove_outliers_iqr(df, 'Unified Demand', ba_col, iqr_factor)
    
    # Step 5: Interpolate missing values
    df = interpolate_missing_values(df, ['Unified Demand'])
    
    # Step 6: Validate peak demands
    df = validate_peak_demand(df, 'Unified Demand', ba_col, peak_threshold)
    
    # Log final statistics
    if ba_col in df.columns:
        logging.info("Final cleaning statistics by BA:")
        stats = df.groupby(ba_col)['Unified Demand'].agg(['count', 'min', 'max', 'mean'])
        for ba, row in stats.iterrows():
            logging.info(f"  {ba}: {row['count']} points, "
                       f"range: {row['min']:.0f}-{row['max']:.0f} MW, "
                       f"mean: {row['mean']:.0f} MW")
    
    logging.info("BA data cleaning pipeline completed")
    return df


def clean_file(input_path: Union[str, Path], 
               output_path: Optional[Union[str, Path]] = None,
               **kwargs) -> pd.DataFrame:
    """
    Clean a single BA aggregate data file.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to save cleaned data (optional)
        **kwargs: Additional arguments for clean_ba_data
        
    Returns:
        Cleaned DataFrame
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    logging.info(f"Cleaning file: {input_path}")
    
    # Load data
    df = pd.read_csv(input_path)
    
    # Rename columns to standard format if needed
    column_mapping = {
        'period': 'Timestamp',
        'value': 'Demand',
        'respondent-name': 'Balancing Authority'
    }
    
    df = df.rename(columns=column_mapping)
    
    # Clean data
    df_cleaned = clean_ba_data(df, **kwargs)
    
    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_cleaned.to_csv(output_path, index=False)
        logging.info(f"Saved cleaned data to: {output_path}")
    
    return df_cleaned


def clean_directory(input_dir: Union[str, Path],
                   output_dir: Union[str, Path],
                   pattern: str = "*.csv",
                   **kwargs) -> Dict[str, pd.DataFrame]:
    """
    Clean all CSV files in a directory.
    
    Args:
        input_dir: Directory containing raw CSV files
        output_dir: Directory to save cleaned files
        pattern: File pattern to match (default: "*.csv")
        **kwargs: Additional arguments for clean_ba_data
        
    Returns:
        Dictionary mapping filenames to cleaned DataFrames
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for file_path in input_dir.glob(pattern):
        try:
            # Generate output filename
            output_file = output_dir / f"cleaned_{file_path.name}"
            
            # Clean file
            df_cleaned = clean_file(file_path, output_file, **kwargs)
            results[file_path.name] = df_cleaned
            
        except Exception as e:
            logging.error(f"Error cleaning {file_path}: {e}")
            continue
    
    logging.info(f"Cleaned {len(results)} files from {input_dir}")
    return results


def main():
    """Example usage of the cleaning module."""
    
    # Example: Clean all files in ba_aggregate_data/raw directory
    try:
        results = clean_directory(
            input_dir="ba_aggregate_data/raw",
            output_dir="ba_aggregate_data/cleaned",
            iqr_factor=3.0,
            peak_threshold=2.0
        )
        
        print(f"Successfully cleaned {len(results)} files")
        
    except FileNotFoundError as e:
        print(f"Directory not found: {e}")
        print("Please ensure ba_aggregate_data/raw directory exists with CSV files")
    
    except Exception as e:
        print(f"Error during cleaning: {e}")


if __name__ == "__main__":
    main()