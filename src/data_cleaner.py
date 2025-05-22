"""Module for cleaning EIA hourly load data according to Appendix B specifications."""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from config import CLEANING_PARAMS, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


class DataCleaner:
    """Cleans EIA hourly load data according to paper specifications."""
    
    def __init__(self, params: Dict = CLEANING_PARAMS):
        """Initialize the data cleaner with cleaning parameters."""
        self.params = params
    
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicate timestamps for each BA.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame without duplicates
        """
        logger.info("Removing duplicate timestamps")
        
        # Sort by timestamp and BA to ensure consistent ordering
        df = df.sort_values(["ba_code", "timestamp"])
        
        # Remove duplicates, keeping the first occurrence
        df_clean = df.drop_duplicates(subset=["ba_code", "timestamp"], keep="first")
        
        removed = len(df) - len(df_clean)
        if removed > 0:
            logger.warning(f"Removed {removed} duplicate records")
        
        return df_clean
    
    def detect_outliers_iqr(self, series: pd.Series, multiplier: float = 1.5) -> pd.Series:
        """
        Detect outliers using Interquartile Range (IQR) method.
        
        Args:
            series: Data series
            multiplier: IQR multiplier for outlier bounds
            
        Returns:
            Boolean series indicating outliers
        """
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        
        return (series < lower_bound) | (series > upper_bound)
    
    def detect_outliers_zscore(self, series: pd.Series, threshold: float = 3) -> pd.Series:
        """
        Detect outliers using Z-score method.
        
        Args:
            series: Data series
            threshold: Z-score threshold
            
        Returns:
            Boolean series indicating outliers
        """
        z_scores = np.abs(stats.zscore(series.dropna()))
        return pd.Series(z_scores > threshold, index=series.dropna().index).reindex(series.index, fill_value=False)
    
    def handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle outliers in load data.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with outliers handled
        """
        logger.info(f"Handling outliers using {self.params['outlier_method']} method")
        
        df_clean = df.copy()
        
        for ba_code in df["ba_code"].unique():
            ba_mask = df_clean["ba_code"] == ba_code
            ba_data = df_clean.loc[ba_mask, "load_mw"]
            
            if self.params["outlier_method"] == "iqr":
                outliers = self.detect_outliers_iqr(
                    ba_data, 
                    multiplier=self.params["iqr_multiplier"]
                )
            elif self.params["outlier_method"] == "zscore":
                outliers = self.detect_outliers_zscore(
                    ba_data,
                    threshold=self.params["outlier_threshold"]
                )
            else:
                raise ValueError(f"Unknown outlier method: {self.params['outlier_method']}")
            
            # Replace outliers with NaN for later interpolation
            df_clean.loc[ba_mask & outliers, "load_mw"] = np.nan
            
            if outliers.sum() > 0:
                logger.info(f"Found {outliers.sum()} outliers for {ba_code}")
    
        return df_clean
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in the data.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with missing values handled
        """
        logger.info(f"Handling missing values using {self.params['handle_missing']} method")
        
        df_clean = df.copy()
        
        # Ensure complete hourly timestamps for each BA
        for ba_code in df["ba_code"].unique():
            ba_mask = df_clean["ba_code"] == ba_code
            ba_data = df_clean[ba_mask].copy()
            
            # Create complete hourly range
            date_range = pd.date_range(
                start=ba_data["timestamp"].min(),
                end=ba_data["timestamp"].max(),
                freq="h"
            )
            
            # Reindex to complete hourly range
            ba_data = ba_data.set_index("timestamp").reindex(date_range)
            ba_data["ba_code"] = ba_code
            ba_data = ba_data.reset_index().rename(columns={"index": "timestamp"})
            
            # Handle missing values
            if self.params["handle_missing"] == "interpolate":
                # Linear interpolation for small gaps, limit to 3 hours
                ba_data["load_mw"] = ba_data["load_mw"].interpolate(
                    method="linear", 
                    limit=3,
                    limit_area="inside"
                )
            elif self.params["handle_missing"] == "forward_fill":
                ba_data["load_mw"] = ba_data["load_mw"].fillna(method="ffill", limit=3)
            elif self.params["handle_missing"] == "drop":
                ba_data = ba_data.dropna(subset=["load_mw"])
            
            # Update the main dataframe
            if ba_mask.sum() > 0:
                df_clean = df_clean[~ba_mask]
            df_clean = pd.concat([df_clean, ba_data], ignore_index=True)
        
        return df_clean.sort_values(["ba_code", "timestamp"])
    
    def validate_data_quality(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        Validate data quality and completeness.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (validated DataFrame, quality metrics)
        """
        logger.info("Validating data quality")
        
        quality_metrics = {}
        valid_bas = []
        
        for ba_code in df["ba_code"].unique():
            ba_data = df[df["ba_code"] == ba_code]
            
            # Calculate completeness
            total_hours = len(ba_data)
            missing_hours = ba_data["load_mw"].isna().sum()
            completeness = 1 - (missing_hours / total_hours)
            
            quality_metrics[ba_code] = {
                "total_hours": total_hours,
                "missing_hours": missing_hours,
                "completeness": completeness,
                "min_load": ba_data["load_mw"].min(),
                "max_load": ba_data["load_mw"].max(),
                "mean_load": ba_data["load_mw"].mean(),
                "std_load": ba_data["load_mw"].std()
            }
            
            # Check if BA meets minimum completeness threshold
            if completeness >= self.params["min_data_completeness"]:
                valid_bas.append(ba_code)
            else:
                logger.warning(
                    f"BA {ba_code} has completeness {completeness:.2%}, "
                    f"below threshold {self.params['min_data_completeness']:.2%}"
                )
        
        # Filter to only valid BAs
        df_valid = df[df["ba_code"].isin(valid_bas)]
        
        return df_valid, quality_metrics
    
    def apply_physical_constraints(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply physical constraints to ensure data validity.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with physical constraints applied
        """
        logger.info("Applying physical constraints")
        
        df_clean = df.copy()
        
        # Ensure non-negative loads
        negative_loads = df_clean["load_mw"] < 0
        if negative_loads.sum() > 0:
            logger.warning(f"Found {negative_loads.sum()} negative load values, setting to 0")
            df_clean.loc[negative_loads, "load_mw"] = 0
        
        # Check for unrealistic load changes (>50% hour-to-hour)
        for ba_code in df_clean["ba_code"].unique():
            ba_mask = df_clean["ba_code"] == ba_code
            ba_data = df_clean[ba_mask].sort_values("timestamp")
            
            # Calculate hour-to-hour changes
            load_change = ba_data["load_mw"].pct_change().abs()
            large_changes = load_change > 0.5
            
            if large_changes.sum() > 0:
                logger.warning(
                    f"Found {large_changes.sum()} large hour-to-hour changes "
                    f"(>50%) for {ba_code}"
                )
        
        return df_clean
    
    def clean_data(self, df: pd.DataFrame, save: bool = True) -> Tuple[pd.DataFrame, Dict]:
        """
        Apply full cleaning pipeline to the data.
        
        Args:
            df: Input DataFrame
            save: Whether to save the cleaned data
            
        Returns:
            Tuple of (cleaned DataFrame, quality metrics)
        """
        logger.info("Starting data cleaning pipeline")
        
        # Ensure proper data types
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["load_mw"] = pd.to_numeric(df["load_mw"], errors="coerce")
        
        # Step 1: Remove duplicates
        if self.params["remove_duplicates"]:
            df = self.remove_duplicates(df)
        
        # Step 2: Handle outliers
        df = self.handle_outliers(df)
        
        # Step 3: Handle missing values
        df = self.handle_missing_values(df)
        
        # Step 4: Apply physical constraints
        df = self.apply_physical_constraints(df)
        
        # Step 5: Validate data quality
        df_clean, quality_metrics = self.validate_data_quality(df)
        
        logger.info(f"Cleaning complete. Retained {len(df_clean['ba_code'].unique())} BAs")
        
        # Save cleaned data
        if save:
            output_path = f"{PROCESSED_DATA_DIR}/cleaned_hourly_load_data.csv"
            df_clean.to_csv(output_path, index=False)
            logger.info(f"Saved cleaned data to {output_path}")
            
            # Save quality metrics
            quality_df = pd.DataFrame(quality_metrics).T
            quality_path = f"{PROCESSED_DATA_DIR}/data_quality_metrics.csv"
            quality_df.to_csv(quality_path)
            logger.info(f"Saved quality metrics to {quality_path}")
        
        return df_clean, quality_metrics


def main():
    """Main function for testing the data cleaner."""
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Load sample data
    raw_data_path = f"{PROCESSED_DATA_DIR}/../raw/all_ba_hourly_load_2016-01-01_2024-12-31.csv"
    
    if os.path.exists(raw_data_path):
        df = pd.read_csv(raw_data_path)
        
        cleaner = DataCleaner()
        df_clean, metrics = cleaner.clean_data(df)
        
        print(f"Cleaned data shape: {df_clean.shape}")
        print("\nData quality metrics:")
        for ba, metric in metrics.items():
            print(f"{ba}: {metric['completeness']:.2%} complete")
    else:
        print(f"Raw data file not found at {raw_data_path}")


if __name__ == "__main__":
    main()