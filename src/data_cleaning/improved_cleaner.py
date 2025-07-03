"""
Improved EIA data cleaner with enhanced readability and maintainability.

This module provides a cleaner implementation of the data cleaning pipeline
with better separation of concerns, comprehensive documentation, and configurable parameters.
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, List, Dict, Tuple

from .constants import (
    CleaningConfig, BA_LABEL_MAPPING, MAX_REASONABLE_DEMAND_GW,
    ERROR_MESSAGES, LOG_MESSAGES, OUTLIER_DETECTION_METHODS
)

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Improved EIA electricity demand data cleaner.
    
    This class provides a structured approach to cleaning EIA data with configurable
    parameters and comprehensive logging. The cleaning pipeline includes:
    1. Datetime normalization
    2. Demand column unification  
    3. BA label mapping
    4. Missing value interpolation
    5. Outlier detection and correction
    6. Spike smoothing
    7. Peak removal
    
    Example:
        >>> config = CleaningConfig(spike_threshold=2.5)
        >>> cleaner = DataCleaner(config)
        >>> clean_data = cleaner.clean(raw_data)
    """
    
    def __init__(self, config: Optional[CleaningConfig] = None):
        """
        Initialize the data cleaner.
        
        Args:
            config: Cleaning configuration. If None, uses default settings.
        """
        self.config = config or CleaningConfig()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging for the cleaning process."""
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean EIA electricity demand data using the full pipeline.
        
        Args:
            df: Raw EIA data DataFrame
            
        Returns:
            Cleaned DataFrame with 'Unified Demand' column
            
        Raises:
            ValueError: If required columns are missing
        """
        logger.info("Starting data cleaning pipeline")
        df_clean = df.copy()
        
        # Step 1: Normalize datetime
        if self.config.datetime_col in df_clean.columns:
            df_clean = self._normalize_datetime(df_clean)
        
        # Step 2: Create unified demand column
        df_clean = self._create_unified_demand(df_clean)
        self._validate_unified_demand(df_clean)
        
        # Step 3: Map BA labels  
        if self.config.ba_col in df_clean.columns:
            df_clean = self._map_ba_labels(df_clean)
        
        # Step 4: Remove extreme outliers first (physically impossible values)
        df_clean = self._remove_extreme_outliers(df_clean)
        
        # Step 5: Interpolate missing values
        if self.config.interpolate_zeros:
            df_clean = self._interpolate_missing_values(df_clean)
        
        # Step 6: Remove low outliers
        if self.config.remove_low_outliers and self.config.ba_col in df_clean.columns:
            df_clean = self._remove_low_outliers(df_clean)
        
        # Step 7: Smooth spikes
        if self.config.correct_spikes:
            df_clean = self._smooth_spikes(df_clean)
        
        # Step 8: Handle erroneous peaks
        if self.config.handle_peaks and self.config.ba_col in df_clean.columns:
            df_clean = self._handle_peaks(df_clean)
        
        self._log_cleaning_summary(df_clean)
        return df_clean
    
    def _normalize_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert datetime column to pandas datetime format."""
        df[self.config.datetime_col] = pd.to_datetime(
            df[self.config.datetime_col], 
            errors='coerce'
        )
        logger.info(LOG_MESSAGES['normalized_datetime'].format(
            col=self.config.datetime_col
        ))
        return df
    
    def _create_unified_demand(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create unified demand column, preferring adjusted values when available.
        
        Priority: Adjusted demand > Primary demand > NaN
        """
        primary_col = self.config.demand_col_primary
        adj_col = self.config.adj_demand_col
        
        if adj_col in df.columns and primary_col in df.columns:
            df["Unified Demand"] = df[adj_col].fillna(df[primary_col])
        elif adj_col in df.columns:
            df["Unified Demand"] = df[adj_col]
        elif primary_col in df.columns:
            df["Unified Demand"] = df[primary_col]
        else:
            df["Unified Demand"] = np.nan
            logger.warning("No demand columns found. Created empty Unified Demand column.")
        
        logger.info(LOG_MESSAGES['created_unified_demand'])
        return df
    
    def _validate_unified_demand(self, df: pd.DataFrame) -> None:
        """Validate that unified demand column was created successfully."""
        if "Unified Demand" not in df.columns or df["Unified Demand"].isnull().all():
            raise ValueError("Failed to create Unified Demand column. Check input columns.")
    
    def _map_ba_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map BA codes to standard names using predefined mapping."""
        df[self.config.ba_col] = df[self.config.ba_col].map(BA_LABEL_MAPPING).fillna(
            df[self.config.ba_col]
        )
        logger.info(LOG_MESSAGES['mapped_ba_labels'].format(col=self.config.ba_col))
        return df
    
    def _interpolate_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fill missing values and zeros using linear interpolation.
        
        Treats zeros as missing data that should be interpolated.
        """
        initial_missing = self._count_missing_and_zeros(df, "Unified Demand")
        
        # Replace zeros with NaN, then interpolate
        df["Unified Demand"] = df["Unified Demand"].replace(0, np.nan)
        df["Unified Demand"] = df["Unified Demand"].interpolate(
            method='linear', 
            limit_direction='both'
        )
        
        final_missing = df["Unified Demand"].isna().sum()
        filled_count = initial_missing - final_missing
        
        logger.info(LOG_MESSAGES['filled_missing_values'].format(count=filled_count))
        return df
    
    def _count_missing_and_zeros(self, df: pd.DataFrame, column: str) -> int:
        """Count missing values and zeros in a column."""
        return df[column].isna().sum() + (df[column] == 0).sum()
    
    def _remove_extreme_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove physically impossible demand values.
        
        Uses configurable detection method to identify extreme outliers
        that are likely data errors rather than real demand spikes.
        """
        if self.config.ba_col in df.columns:
            return self._remove_outliers_per_ba(df)
        else:
            return self._remove_outliers_global(df)
    
    def _remove_outliers_per_ba(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove extreme outliers within each BA separately."""
        df_clean = df.copy()
        total_outliers = 0
        
        for ba in df[self.config.ba_col].unique():
            ba_mask = df[self.config.ba_col] == ba
            ba_data = df.loc[ba_mask, "Unified Demand"]
            
            outlier_mask = self._detect_extreme_outliers(ba_data)
            
            if outlier_mask.sum() > 0:
                logger.warning(f"BA {ba}: Found {outlier_mask.sum()} extreme outliers")
                df_clean.loc[ba_mask & outlier_mask, "Unified Demand"] = np.nan
                total_outliers += outlier_mask.sum()
        
        # Interpolate removed outliers
        if total_outliers > 0:
            df_clean = self._interpolate_by_ba(df_clean)
            logger.info(f"Removed {total_outliers} extreme outliers using {self.config.outlier_method}")
        
        return df_clean
    
    def _remove_outliers_global(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove extreme outliers globally (when no BA column available)."""
        outlier_mask = self._detect_extreme_outliers(df["Unified Demand"])
        
        if outlier_mask.sum() > 0:
            df["Unified Demand"] = df["Unified Demand"].mask(outlier_mask)
            df["Unified Demand"] = df["Unified Demand"].interpolate(
                method='linear', limit_direction='both'
            )
            logger.info(f"Removed {outlier_mask.sum()} extreme outliers globally")
        
        return df
    
    def _detect_extreme_outliers(self, series: pd.Series) -> pd.Series:
        """
        Detect extreme outliers using the configured method.
        
        Args:
            series: Data series to analyze
            
        Returns:
            Boolean series indicating outlier positions
        """
        clean_series = series.dropna()
        
        if len(clean_series) < 10:  # Need minimum data points
            return pd.Series(False, index=series.index)
        
        if self.config.outlier_method == "iqr_extreme":
            return self._detect_outliers_iqr(series, clean_series)
        elif self.config.outlier_method == "mad":
            return self._detect_outliers_mad(series, clean_series)
        elif self.config.outlier_method == "zscore":
            return self._detect_outliers_zscore(series, clean_series)
        else:
            raise ValueError(f"Unknown outlier method: {self.config.outlier_method}")
    
    def _detect_outliers_iqr(self, series: pd.Series, clean_series: pd.Series) -> pd.Series:
        """Detect outliers using Interquartile Range method."""
        # Remove obvious extreme outliers first to avoid contamination
        median = clean_series.median()
        obvious_outliers = clean_series > (median * 3)
        
        if obvious_outliers.any():
            clean_series = clean_series[~obvious_outliers]
        
        # Calculate robust statistics
        Q1 = clean_series.quantile(0.25)
        Q3 = clean_series.quantile(0.75)
        IQR = Q3 - Q1
        median_clean = clean_series.median()
        
        # Calculate conservative bounds
        iqr_bound = Q3 + 3 * IQR
        median_bound = median_clean * 2.5
        p90_bound = clean_series.quantile(0.90) * 1.5
        
        # Use most restrictive bound
        upper_bound = min(iqr_bound, median_bound, p90_bound)
        upper_bound = min(upper_bound, MAX_REASONABLE_DEMAND_GW * 1000)  # Convert GW to MW
        
        return series > upper_bound
    
    def _detect_outliers_mad(self, series: pd.Series, clean_series: pd.Series) -> pd.Series:
        """Detect outliers using Median Absolute Deviation."""
        median = clean_series.median()
        mad = np.median(np.abs(clean_series - median))
        
        if mad == 0:  # Fall back to IQR if MAD is 0
            return self._detect_outliers_iqr(series, clean_series)
        
        modified_z_scores = 0.6745 * (series - median) / mad
        return np.abs(modified_z_scores) > 10  # Conservative threshold
    
    def _detect_outliers_zscore(self, series: pd.Series, clean_series: pd.Series) -> pd.Series:
        """Detect outliers using Z-score method."""
        z_scores = np.abs((series - series.mean()) / series.std())
        return z_scores > 6  # Conservative threshold
    
    def _interpolate_by_ba(self, df: pd.DataFrame) -> pd.DataFrame:
        """Interpolate missing values within each BA group."""
        for ba in df[self.config.ba_col].unique():
            ba_mask = df[self.config.ba_col] == ba
            df.loc[ba_mask, "Unified Demand"] = df.loc[ba_mask, "Unified Demand"].interpolate(
                method='linear', limit_direction='both'
            )
        return df
    
    def _remove_low_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove unrealistically low demand values within each BA.
        
        Values below threshold percentage of BA mean are considered outliers.
        """
        if not all(col in df.columns for col in [
            "Unified Demand", self.config.ba_col, self.config.datetime_col
        ]):
            logger.warning(ERROR_MESSAGES['missing_demand_col'].format(
                col="required columns", operation="low outlier removal"
            ))
            return df
        
        # Sort for proper forward/backward fill
        df_sorted = df.sort_values([self.config.ba_col, self.config.datetime_col])
        
        def clean_ba_low_outliers(group):
            mean_demand = group["Unified Demand"].mean()
            if pd.isna(mean_demand):
                return group
            
            threshold = self.config.low_outlier_threshold * mean_demand
            outlier_mask = group["Unified Demand"] < threshold
            
            group_clean = group.copy()
            group_clean.loc[outlier_mask, "Unified Demand"] = np.nan
            group_clean["Unified Demand"] = group_clean["Unified Demand"].ffill().bfill()
            
            return group_clean
        
        result = df_sorted.groupby(self.config.ba_col, group_keys=False, dropna=False).apply(
            clean_ba_low_outliers
        )
        
        outliers_removed = (df["Unified Demand"] != result["Unified Demand"]).sum()
        logger.info(LOG_MESSAGES['imputed_outliers'].format(count=outliers_removed))
        
        return result.reset_index(drop=True)
    
    def _smooth_spikes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Smooth demand spikes using rolling window statistics.
        
        Replaces values beyond threshold standard deviations with rolling mean.
        """
        if "Unified Demand" not in df.columns:
            logger.warning(ERROR_MESSAGES['missing_demand_col'].format(
                col="Unified Demand", operation="spike correction"
            ))
            return df
        
        if self.config.ba_col in df.columns:
            return self._smooth_spikes_per_ba(df)
        else:
            logger.warning(ERROR_MESSAGES['missing_ba_col'].format(
                col=self.config.ba_col, operation="spike correction"
            ))
            return self._smooth_spikes_global(df)
    
    def _smooth_spikes_per_ba(self, df: pd.DataFrame) -> pd.DataFrame:
        """Smooth spikes within each BA separately."""
        return df.groupby(self.config.ba_col, group_keys=False, dropna=False).apply(
            self._apply_spike_smoothing
        )
    
    def _smooth_spikes_global(self, df: pd.DataFrame) -> pd.DataFrame:
        """Smooth spikes globally (when no BA grouping available)."""
        return self._apply_spike_smoothing(df)
    
    def _apply_spike_smoothing(self, group: pd.DataFrame) -> pd.DataFrame:
        """Apply spike smoothing to a data group."""
        group_clean = group.copy()
        
        # Calculate rolling statistics
        rolling_mean = group_clean["Unified Demand"].rolling(
            window=self.config.spike_window_size, 
            center=True, 
            min_periods=1
        ).mean()
        
        rolling_std = group_clean["Unified Demand"].rolling(
            window=self.config.spike_window_size, 
            center=True, 
            min_periods=1
        ).std()
        
        # Identify spikes
        upper_limit = rolling_mean + self.config.spike_threshold * rolling_std
        lower_limit = rolling_mean - self.config.spike_threshold * rolling_std
        
        spike_mask = (
            (group_clean["Unified Demand"] > upper_limit) | 
            (group_clean["Unified Demand"] < lower_limit)
        )
        
        # Replace spikes with rolling mean
        group_clean.loc[spike_mask, "Unified Demand"] = rolling_mean[spike_mask]
        
        return group_clean
    
    def _handle_peaks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove extreme peaks that exceed multiple of BA's historical maximum.
        
        Note: Current implementation has limitations due to using transform('max')
        which includes the peak in its own threshold calculation.
        """
        if not all(col in df.columns for col in ["Unified Demand", self.config.ba_col]):
            logger.warning(ERROR_MESSAGES['missing_demand_col'].format(
                col="required columns", operation="peak handling"
            ))
            return df
        
        df_clean = df.copy()
        
        # Calculate threshold per BA
        ba_max = df_clean.groupby(self.config.ba_col, dropna=False)["Unified Demand"].transform('max')
        threshold = ba_max * self.config.peak_threshold
        
        # Identify and remove peaks
        peak_mask = df_clean["Unified Demand"] > threshold
        peaks_removed = peak_mask.sum()
        
        if peaks_removed > 0:
            df_clean.loc[peak_mask, "Unified Demand"] = np.nan
            df_clean = self._interpolate_by_ba(df_clean)
            logger.info(LOG_MESSAGES['removed_peaks'].format(count=peaks_removed))
        
        return df_clean
    
    def _log_cleaning_summary(self, df: pd.DataFrame) -> None:
        """Log summary of cleaning results."""
        ba_count = df[self.config.ba_col].nunique() if self.config.ba_col in df.columns else 0
        record_count = len(df)
        
        logger.info(LOG_MESSAGES['processing_complete'].format(
            ba_count=ba_count, 
            record_count=record_count
        ))
        
        # Log summary statistics
        if self.config.ba_col in df.columns:
            summary = df.groupby(self.config.ba_col)["Unified Demand"].agg(['min', 'max', 'mean', 'count'])
            logger.info("Summary statistics by BA:")
            for ba, stats in summary.iterrows():
                logger.info(f"  {ba}: min={stats['min']:.0f}, max={stats['max']:.0f}, "
                          f"mean={stats['mean']:.0f}, count={stats['count']}")


# Convenience function for backward compatibility
def clean_eia_data(df_raw: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    Clean EIA data using improved cleaner with backward compatibility.
    
    Args:
        df_raw: Raw EIA data
        **kwargs: Configuration parameters (maps to CleaningConfig fields)
        
    Returns:
        Cleaned DataFrame
    """
    # Map old parameter names to new config structure
    config_params = {}
    
    # Direct parameter mappings
    param_mappings = {
        'datetime_col': 'datetime_col',
        'demand_col_primary': 'demand_col_primary', 
        'adj_demand_col_name': 'adj_demand_col',
        'ba_col': 'ba_col',
        'low_outlier_threshold_factor': 'low_outlier_threshold',
        'spike_window_size': 'spike_window_size',
        'spike_threshold_factor': 'spike_threshold',
        'peak_threshold_factor': 'peak_threshold'
    }
    
    for old_name, new_name in param_mappings.items():
        if old_name in kwargs:
            config_params[new_name] = kwargs[old_name]
    
    config = CleaningConfig(**config_params)
    cleaner = DataCleaner(config)
    
    return cleaner.clean(df_raw)