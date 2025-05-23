import pandas as pd
import numpy as np
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def normalize_datetime(df: pd.DataFrame, datetime_column: str) -> pd.DataFrame:
    """
    Normalizes the specified date-time column in a DataFrame to pandas datetime64[ns] format.

    Args:
        df: The input DataFrame.
        datetime_column: The name of the column containing date-time information.

    Returns:
        The DataFrame with the date-time column normalized.
    """
    df[datetime_column] = pd.to_datetime(df[datetime_column])
    return df

def select_demand_value(df: pd.DataFrame, demand_col: str = 'Demand', adj_demand_col: str = 'Adjusted demand') -> pd.DataFrame:
    """
    Selects the demand value based on specified demand and adjusted demand columns.
    Creates a new "Unified Demand" column.

    Args:
        df: The input DataFrame.
        demand_col: The name of the primary demand column.
        adj_demand_col: The name of the adjusted demand column.

    Returns:
        The DataFrame with the "Unified Demand" column.
    """
    # Ensure columns exist to avoid KeyErrors
    has_demand = demand_col in df.columns
    has_adj_demand = adj_demand_col in df.columns

    if has_adj_demand and has_demand:
        df["Unified Demand"] = np.where(df[adj_demand_col].notnull(), df[adj_demand_col], df[demand_col])
    elif has_adj_demand: # Only adjusted demand exists
        df["Unified Demand"] = df[adj_demand_col]
    elif has_demand: # Only primary demand exists
        df["Unified Demand"] = df[demand_col]
    else: # Neither column exists
        # This case should be handled by the caller, but as a fallback:
        df["Unified Demand"] = np.nan 
    return df

def map_ba_labels(df: pd.DataFrame, ba_column: str) -> pd.DataFrame:
    """
    Maps Balancing Authority (BA) labels to a standard set of acronyms.

    Args:
        df: The input DataFrame.
        ba_column: The name of the column containing BA labels.

    Returns:
        The DataFrame with BA labels mapped to standard acronyms.
    """
    ba_mapping = {
        "CPLE": "DEP", "DUK": "DEC", "SC": "SCP", "SWPP": "SPP",
        "SCEG": "DESC", "FPC": "DEF", "CISO": "CAISO", "BPAT": "BPA",
        "NYIS": "NYISO", "ERCO": "ERCOT",
        # Add more mappings as needed
    }
    df[ba_column] = df[ba_column].map(ba_mapping).fillna(df[ba_column])
    return df

def fill_missing_zeros_linear_interpolation(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Replaces NaN values and zero values in specified columns using linear interpolation.

    Args:
        df: The input DataFrame.
        columns: A list of column names to process.

    Returns:
        The DataFrame with missing values and zeros interpolated.
    """
    for col in columns:
        if col in df.columns:
            df[col] = df[col].replace(0, np.nan)
            df[col] = df[col].interpolate(method='linear', limit_direction='both')
        else:
            logging.warning(f"Column '{col}' not found for interpolation. Skipping.")
    return df

def impute_low_outliers(df: pd.DataFrame, demand_column: str, ba_column: str, datetime_column: str, threshold_factor: float = 0.1) -> pd.DataFrame:
    """
    Imputes low outliers in the demand column for each Balancing Authority (BA).

    Args:
        df: The input DataFrame.
        demand_column: The name of the demand column.
        ba_column: The name of the Balancing Authority column.
        datetime_column: The name of the date-time column (used for sorting).
        threshold_factor: The factor to determine the low threshold (e.g., 0.1 for 10% of mean).

    Returns:
        The DataFrame with low outliers imputed.
    """
    if not all(col in df.columns for col in [demand_column, ba_column, datetime_column]):
        logging.warning("One or more required columns for impute_low_outliers not found. Skipping.")
        return df
        
    df = df.sort_values(by=[ba_column, datetime_column])
    
    imputed_dfs = []
    for _, group in df.groupby(ba_column, group_keys=False, dropna=False): # dropna=False to keep groups with NaN BA keys if any
        # Ensure group is a DataFrame, not a Series if only one column was selected by mistake
        if isinstance(group, pd.Series): group = group.to_frame()

        mean_demand = group[demand_column].mean()
        if pd.isna(mean_demand): # Skip if mean_demand is NaN (e.g., all NaNs in group)
            imputed_dfs.append(group)
            continue

        low_threshold = threshold_factor * mean_demand
        
        is_outlier = group[demand_column] < low_threshold
        group_copy = group.copy() # Avoid SettingWithCopyWarning
        group_copy.loc[is_outlier, demand_column] = np.nan
        
        group_copy[demand_column] = group_copy[demand_column].ffill().bfill()
        imputed_dfs.append(group_copy)
    
    if not imputed_dfs: return df
        
    return pd.concat(imputed_dfs).reset_index(drop=True)


def correct_demand_spikes(df: pd.DataFrame, demand_column: str, ba_column: str = None, window_size: int = 3, threshold_factor: float = 3.0) -> pd.DataFrame:
    """
    Corrects demand spikes using a rolling window standard deviation.
    Operates per BA if ba_column is provided, otherwise globally.
    """
    if demand_column not in df.columns:
        logging.warning(f"Demand column '{demand_column}' not found for correct_demand_spikes. Skipping.")
        return df

    def _correct_spikes_group(group: pd.DataFrame) -> pd.DataFrame:
        group_copy = group.copy() # Work on a copy
        rolling_mean = group_copy[demand_column].rolling(window=window_size, center=True, min_periods=1).mean()
        rolling_std = group_copy[demand_column].rolling(window=window_size, center=True, min_periods=1).std()
        
        is_spike = (group_copy[demand_column] > rolling_mean + threshold_factor * rolling_std) | \
                   (group_copy[demand_column] < rolling_mean - threshold_factor * rolling_std)
        
        group_copy.loc[is_spike, demand_column] = rolling_mean[is_spike]
        return group_copy

    if ba_column and ba_column in df.columns:
        # Using apply on groupby object. _correct_spikes_group receives a DataFrame.
        return df.groupby(ba_column, group_keys=False, dropna=False).apply(_correct_spikes_group)
    else:
        if ba_column and ba_column not in df.columns:
             logging.warning(f"BA column '{ba_column}' not found for spike correction. Performing global correction.")
        return _correct_spikes_group(df) # df.copy() is handled in _correct_spikes_group

def handle_erroneous_peaks(df: pd.DataFrame, demand_column: str, ba_column: str, peak_threshold_factor: float = 2.0) -> pd.DataFrame:
    """
    Handles erroneous peaks by replacing values exceeding a dynamic threshold
    (e.g., 2x the historical max for that BA) with linear interpolation.
    """
    if not all(col in df.columns for col in [demand_column, ba_column]):
        logging.warning("Demand or BA column not found for handle_erroneous_peaks. Skipping.")
        return df

    df_out = df.copy()
    
    historical_max_per_ba = df_out.groupby(ba_column, group_keys=False, dropna=False)[demand_column].transform('max')
    peak_threshold = historical_max_per_ba * peak_threshold_factor
    
    is_peak = df_out[demand_column] > peak_threshold
    df_out.loc[is_peak, demand_column] = np.nan
        
    # Interpolate per group using transform to maintain original index
    # This also handles cases where a group might be all NaNs after peak removal (no change then)
    df_out[demand_column] = df_out.groupby(ba_column, group_keys=False, dropna=False)[demand_column].transform(
        lambda x: x.interpolate(method='linear', limit_direction='both')
    )
    
    return df_out


def clean_eia_data(
    df_raw: pd.DataFrame,
    datetime_col: str = 'Timestamp',
    demand_col_primary: str = 'Demand', # Renamed to avoid conflict with internal 'demand_col' vars
    adj_demand_col_name: str = 'Adjusted demand', # Renamed
    ba_col: str = 'Balancing Authority',
    interp_cols_user: list[str] = None, # Renamed
    low_outlier_threshold_factor: float = 0.1,
    spike_window_size: int = 3,
    spike_threshold_factor: float = 3.0,
    peak_threshold_factor: float = 2.0,
    perform_validation: bool = False
) -> pd.DataFrame:
    """
    Cleans raw EIA data by normalizing columns, handling outliers, and optionally logging validation statistics.

    Args:
        df_raw: The raw EIA DataFrame.
        datetime_col: Name of the column with datetime information.
        demand_col_primary: Name of the primary demand column (e.g., 'Demand').
        adj_demand_col_name: Name of the adjusted demand column (e.g., 'Adjusted demand').
        ba_col: Name of the Balancing Authority column.
        interp_cols_user: List of columns for fill_missing_zeros_linear_interpolation. 
                          Defaults to ['Unified Demand'] if None.
        low_outlier_threshold_factor: Factor for imputing low outliers.
        spike_window_size: Window size for spike correction.
        spike_threshold_factor: Threshold factor for spike correction.
        peak_threshold_factor: Threshold factor for handling erroneous peaks.
        perform_validation: If True, logs details about corrections and summary statistics.

    Returns:
        A cleaned pandas DataFrame.
    """
    df = df_raw.copy()
    unified_demand_col = "Unified Demand" # Internal standard name

    # 1. Normalize data
    if datetime_col not in df.columns:
        logging.warning(f"Datetime column '{datetime_col}' not found. Skipping datetime normalization.")
    else:
        df = normalize_datetime(df, datetime_col)
        if perform_validation: logging.info(f"Normalized datetime column: {datetime_col}")

    # Select demand value (creates 'Unified Demand')
    # Pass the user-specified column names to select_demand_value
    df = select_demand_value(df, demand_col=demand_col_primary, adj_demand_col=adj_demand_col_name)
    if unified_demand_col not in df.columns or df[unified_demand_col].isnull().all():
        logging.error(f"'{unified_demand_col}' column could not be created or is all NaN. Check input demand columns ('{demand_col_primary}', '{adj_demand_col_name}'). Aborting further cleaning.")
        return df
    if perform_validation: logging.info(f"Selected demand value into column: {unified_demand_col}")
    
    interp_cols_to_use = interp_cols_user if interp_cols_user is not None else [unified_demand_col]

    can_do_ba_specific_cleaning = False
    if ba_col not in df.columns:
        logging.warning(f"BA column '{ba_col}' not found. Skipping BA label mapping and BA-specific outlier processing.")
    else:
        df = map_ba_labels(df, ba_col)
        if perform_validation: logging.info(f"Mapped BA labels in column: {ba_col}")
        can_do_ba_specific_cleaning = True

    # Store counts for validation logging
    original_nans = 0
    original_zeros = 0
    if perform_validation and unified_demand_col in df.columns:
        original_nans = df[unified_demand_col].isna().sum()
        original_zeros = (df[unified_demand_col] == 0).sum()

    # 2. Handle outliers
    df = fill_missing_zeros_linear_interpolation(df, columns=interp_cols_to_use)
    if perform_validation and unified_demand_col in df.columns:
        current_nans_after_interp = df[unified_demand_col].isna().sum()
        filled_count = (original_nans + original_zeros) - current_nans_after_interp # Approx.
        logging.info(f"Filled missing/zeros in {interp_cols_to_use} via interpolation. Approx '{unified_demand_col}' values filled: {filled_count}")

    # Store state for validation diffs
    demand_before_step = df[unified_demand_col].copy() if perform_validation and unified_demand_col in df.columns else None

    if can_do_ba_specific_cleaning and datetime_col in df.columns:
        df = impute_low_outliers(df, demand_column=unified_demand_col, ba_column=ba_col, 
                                 datetime_column=datetime_col, threshold_factor=low_outlier_threshold_factor)
        if perform_validation and demand_before_step is not None:
            changed_count = (demand_before_step.fillna(-99999) != df[unified_demand_col].fillna(-99999)).sum()
            logging.info(f"Imputed low outliers in '{unified_demand_col}'. Approx values changed: {changed_count}")
            demand_before_step = df[unified_demand_col].copy()
    elif perform_validation:
        logging.warning(f"Skipping low outlier imputation due to missing BA column ('{ba_col}') or datetime column ('{datetime_col}').")

    spike_correction_ba_param = ba_col if can_do_ba_specific_cleaning else None
    df = correct_demand_spikes(df, demand_column=unified_demand_col, ba_column=spike_correction_ba_param, 
                               window_size=spike_window_size, threshold_factor=spike_threshold_factor)
    if perform_validation and demand_before_step is not None:
        changed_count = (demand_before_step.fillna(-99999) != df[unified_demand_col].fillna(-99999)).sum()
        logging.info(f"Corrected demand spikes in '{unified_demand_col}'. Approx values changed: {changed_count}")
        demand_before_step = df[unified_demand_col].copy()

    if can_do_ba_specific_cleaning:
        df = handle_erroneous_peaks(df, demand_column=unified_demand_col, ba_column=ba_col, 
                                    peak_threshold_factor=peak_threshold_factor)
        if perform_validation and demand_before_step is not None:
            changed_count = (demand_before_step.fillna(-99999) != df[unified_demand_col].fillna(-99999)).sum()
            logging.info(f"Handled erroneous peaks in '{unified_demand_col}'. Approx values changed: {changed_count}")
    elif perform_validation:
         logging.warning(f"Skipping erroneous peak handling due to missing BA column ('{ba_col}').")

    # 3. Log summary statistics
    if perform_validation and unified_demand_col in df.columns:
        if can_do_ba_specific_cleaning:
            logging.info(f"Summary statistics for cleaned '{unified_demand_col}' per BA:")
            summary_stats = df.groupby(ba_col, dropna=False)[unified_demand_col].agg(['min', 'max', 'mean', 'median', 'count'])
            for ba_name_stat, stats in summary_stats.iterrows():
                logging.info(f"BA: {ba_name_stat} - Min: {stats['min']:.2f}, Max: {stats['max']:.2f}, Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}, Count: {stats['count']}")
        else: # Global summary
            logging.info(f"Global summary statistics for cleaned '{unified_demand_col}':")
            stats = df[unified_demand_col].agg(['min', 'max', 'mean', 'median', 'count'])
            logging.info(f"Min: {stats['min']:.2f}, Max: {stats['max']:.2f}, Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}, Count: {stats['count']}")
            
    return df
