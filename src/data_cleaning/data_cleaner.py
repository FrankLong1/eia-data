"""
Improved EIA data cleaner with better readability.
"""

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# BA label mappings - moved to top for visibility
BA_MAPPING = {
    "CPLE": "DEP", "DUK": "DEC", "SC": "SCP", "SWPP": "SPP",
    "SCEG": "DESC", "FPC": "DEF", "CISO": "CAISO", "BPAT": "BPA",
    "NYIS": "NYISO", "ERCO": "ERCOT", "ISNE": "ISO-NE"
}


def normalize_datetime(df: pd.DataFrame, datetime_column: str) -> pd.DataFrame:
    """Convert datetime column to pandas datetime format."""
    df[datetime_column] = pd.to_datetime(df[datetime_column], errors='coerce')
    return df


def select_demand_value(df: pd.DataFrame, demand_col: str = 'Demand', 
                       adj_demand_col: str = 'Adjusted demand') -> pd.DataFrame:
    """
    Creates unified demand column, preferring adjusted values when available.
    Uses adjusted demand if present, otherwise falls back to primary demand.
    """
    # Simplified logic - use adjusted if available, otherwise use primary
    if adj_demand_col in df.columns and demand_col in df.columns:
        df["Unified Demand"] = df[adj_demand_col].fillna(df[demand_col])
    elif adj_demand_col in df.columns:
        df["Unified Demand"] = df[adj_demand_col]
    elif demand_col in df.columns:
        df["Unified Demand"] = df[demand_col]
    else:
        df["Unified Demand"] = np.nan
        
    return df


def map_ba_labels(df: pd.DataFrame, ba_column: str) -> pd.DataFrame:
    """Maps BA codes to standard names using predefined mapping."""
    df[ba_column] = df[ba_column].map(BA_MAPPING).fillna(df[ba_column])
    return df


def fill_missing_zeros_linear_interpolation(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Fills missing values and zeros using linear interpolation.
    Treats zeros as missing data to be interpolated.
    """
    for col in columns:
        if col not in df.columns:
            logging.warning(f"Column '{col}' not found for interpolation. Skipping.")
            continue
            
        # Replace zeros with NaN, then interpolate
        df[col] = df[col].replace(0, np.nan)
        df[col] = df[col].interpolate(method='linear', limit_direction='both')
    
    return df


def impute_low_outliers(df: pd.DataFrame, demand_column: str, ba_column: str, 
                       datetime_column: str, threshold_factor: float = 0.1) -> pd.DataFrame:
    """
    Removes unrealistically low demand values (below threshold % of BA mean).
    Replaces with forward/backward fill within each BA.
    """
    required_cols = [demand_column, ba_column, datetime_column]
    if not all(col in df.columns for col in required_cols):
        logging.warning("One or more required columns for impute_low_outliers not found. Skipping.")
        return df
    
    # Sort by BA and time for proper filling
    df = df.sort_values([ba_column, datetime_column])
    
    # Process each BA separately
    def clean_ba_outliers(group):
        mean_demand = group[demand_column].mean()
        if pd.isna(mean_demand):
            return group
        
        # Mark values below threshold as outliers
        threshold = threshold_factor * mean_demand
        mask = group[demand_column] < threshold
        
        # Replace outliers and fill
        group = group.copy()
        group.loc[mask, demand_column] = np.nan
        group[demand_column] = group[demand_column].ffill().bfill()
        
        return group
    
    # Apply to each BA
    result = df.groupby(ba_column, group_keys=False, dropna=False).apply(clean_ba_outliers)
    return result.reset_index(drop=True)


def correct_demand_spikes(df: pd.DataFrame, demand_column: str, ba_column: str = None, 
                         window_size: int = 3, threshold_factor: float = 3.0) -> pd.DataFrame:
    """
    Smooths demand spikes using rolling window statistics.
    Replaces values beyond N standard deviations with rolling mean.
    """
    if demand_column not in df.columns:
        logging.warning(f"Demand column '{demand_column}' not found for correct_demand_spikes. Skipping.")
        return df
    
    def smooth_spikes(group):
        group = group.copy()
        
        # Calculate rolling statistics
        rolling_mean = group[demand_column].rolling(
            window=window_size, center=True, min_periods=1
        ).mean()
        rolling_std = group[demand_column].rolling(
            window=window_size, center=True, min_periods=1
        ).std()
        
        # Find spikes (beyond threshold std devs)
        upper_limit = rolling_mean + threshold_factor * rolling_std
        lower_limit = rolling_mean - threshold_factor * rolling_std
        is_spike = (group[demand_column] > upper_limit) | (group[demand_column] < lower_limit)
        
        # Replace spikes with rolling mean
        group.loc[is_spike, demand_column] = rolling_mean[is_spike]
        return group
    
    # Apply per BA or globally
    if ba_column and ba_column in df.columns:
        return df.groupby(ba_column, group_keys=False, dropna=False).apply(smooth_spikes)
    else:
        if ba_column:
            logging.warning(f"BA column '{ba_column}' not found. Applying global spike correction.")
        return smooth_spikes(df)


def handle_erroneous_peaks(df: pd.DataFrame, demand_column: str, ba_column: str, 
                          peak_threshold_factor: float = 2.0) -> pd.DataFrame:
    """
    Removes extreme peaks that exceed a multiple of BA's historical maximum.
    Note: Current implementation has a limitation where the peak itself influences
    the threshold. Consider using quantiles instead of max for better detection.
    """
    if not all(col in df.columns for col in [demand_column, ba_column]):
        logging.warning("Demand or BA column not found for handle_erroneous_peaks. Skipping.")
        return df
    
    df = df.copy()
    
    # Calculate max per BA (includes the peak itself - limitation)
    ba_max = df.groupby(ba_column, dropna=False)[demand_column].transform('max')
    threshold = ba_max * peak_threshold_factor
    
    # Replace extreme values
    mask = df[demand_column] > threshold
    df.loc[mask, demand_column] = np.nan
    
    # Interpolate within each BA
    df[demand_column] = df.groupby(ba_column, dropna=False)[demand_column].transform(
        lambda x: x.interpolate(method='linear', limit_direction='both')
    )
    
    return df


def clean_eia_data(
    df_raw: pd.DataFrame,
    datetime_col: str = 'Timestamp',
    demand_col_primary: str = 'Demand',
    adj_demand_col_name: str = 'Adjusted demand',
    ba_col: str = 'Balancing Authority',
    interp_cols_user: list[str] = None,
    low_outlier_threshold_factor: float = 0.1,
    spike_window_size: int = 3,
    spike_threshold_factor: float = 3.0,
    peak_threshold_factor: float = 2.0
) -> pd.DataFrame:
    """
    Main cleaning pipeline for EIA electricity demand data.
    
    Steps:
    1. Normalize datetime column
    2. Create unified demand column from primary/adjusted values  
    3. Map BA codes to standard names
    4. Interpolate zeros and missing values
    5. Remove low outliers (< 10% of BA mean)
    6. Smooth demand spikes (beyond 3 std devs)
    7. Remove extreme peaks (> 2x BA max)
    
    Args:
        df_raw: Raw EIA data
        datetime_col: Datetime column name
        demand_col_primary: Primary demand column
        adj_demand_col_name: Adjusted demand column (may not exist)
        ba_col: Balancing authority column
        interp_cols_user: Columns to interpolate (default: Unified Demand)
        low_outlier_threshold_factor: Threshold for low outliers (0.1 = 10% of mean)
        spike_window_size: Rolling window size for spike detection
        spike_threshold_factor: Std dev threshold for spikes
        peak_threshold_factor: Multiple of max for peak detection
        
    Returns:
        Cleaned DataFrame with 'Unified Demand' column
    """
    df = df_raw.copy()
    
    # Step 1: Normalize datetime
    if datetime_col in df.columns:
        df = normalize_datetime(df, datetime_col)
        logging.info(f"Normalized datetime column: {datetime_col}")
    
    # Step 2: Create unified demand
    df = select_demand_value(df, demand_col_primary, adj_demand_col_name)
    
    if "Unified Demand" not in df.columns or df["Unified Demand"].isnull().all():
        logging.error("Failed to create Unified Demand column. Check input columns.")
        return df
    
    logging.info("Created Unified Demand column")
    
    # Step 3: Map BA labels
    if ba_col in df.columns:
        df = map_ba_labels(df, ba_col)
        logging.info(f"Mapped BA labels in column: {ba_col}")
    
    # Track cleaning progress
    initial_nans = df["Unified Demand"].isna().sum()
    initial_zeros = (df["Unified Demand"] == 0).sum()
    
    # Step 4: Interpolate missing/zero values
    columns_to_interpolate = interp_cols_user or ["Unified Demand"]
    df = fill_missing_zeros_linear_interpolation(df, columns_to_interpolate)
    
    # Tracks the number of missing/zero values filled via interpolation
    current_nans = df["Unified Demand"].isna().sum()
    filled = (initial_nans + initial_zeros) - current_nans
    logging.info(f"Filled {filled} missing/zero values via interpolation")
    
    if ba_col not in df.columns:
        logging.warning(f"BA column '{ba_col}' not found. Skipping BA-specific cleaning.")
    else:
        # Step 5: Remove low outliers
        if datetime_col in df.columns:
            pre_outlier = df["Unified Demand"].copy()
            
            df = impute_low_outliers(
                df, "Unified Demand", ba_col, datetime_col, 
                threshold_factor=low_outlier_threshold_factor
            )
            
            changed = (pre_outlier != df["Unified Demand"]).sum()
            logging.info(f"Imputed {changed} low outliers")
        
        # Step 6: Smooth spikes
        pre_spike = df["Unified Demand"].copy()
        
        df = correct_demand_spikes(
            df, "Unified Demand", ba_col,
            window_size=spike_window_size,
            threshold_factor=spike_threshold_factor
        )
        
        changed = (pre_spike != df["Unified Demand"]).sum()
        logging.info(f"Smoothed {changed} demand spikes")
        
        # Step 7: Remove extreme peaks
        pre_peak = df["Unified Demand"].copy()
        
        df = handle_erroneous_peaks(
            df, "Unified Demand", ba_col,
            peak_threshold_factor=peak_threshold_factor
        )
        
        changed = (pre_peak != df["Unified Demand"]).sum()
        logging.info(f"Removed {changed} extreme peaks")
    
    # Log summary statistics
    if ba_col in df.columns:
        logging.info("Summary statistics by BA:")
        summary = df.groupby(ba_col)["Unified Demand"].agg(['min', 'max', 'mean', 'count'])
        for ba, stats in summary.iterrows():
            logging.info(f"  {ba}: min={stats['min']:.0f}, max={stats['max']:.0f}, "
                       f"mean={stats['mean']:.0f}, count={stats['count']}")
    else:
        stats = df["Unified Demand"].agg(['min', 'max', 'mean', 'count'])
        logging.info(f"Global stats: min={stats['min']:.0f}, max={stats['max']:.0f}, "
                   f"mean={stats['mean']:.0f}, count={stats['count']}")
    
    return df