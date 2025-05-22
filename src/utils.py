"""Utility functions for the EIA data pipeline."""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level
        log_file: Optional log file path
    """
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )


def validate_date_range(start_date: str, end_date: str) -> bool:
    """
    Validate date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        return start <= end
    except ValueError:
        return False


def create_date_chunks(start_date: str, end_date: str, 
                      chunk_days: int = 365) -> List[tuple]:
    """
    Create date chunks for batch processing.
    
    Args:
        start_date: Start date
        end_date: End date
        chunk_days: Days per chunk
        
    Returns:
        List of (start, end) date tuples
    """
    chunks = []
    current_start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    while current_start < end:
        chunk_end = min(
            current_start + pd.Timedelta(days=chunk_days - 1),
            end
        )
        chunks.append((
            current_start.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d")
        ))
        current_start = chunk_end + pd.Timedelta(days=1)
    
    return chunks


def merge_data_files(file_paths: List[str], output_path: str) -> pd.DataFrame:
    """
    Merge multiple CSV files.
    
    Args:
        file_paths: List of file paths to merge
        output_path: Output file path
        
    Returns:
        Merged DataFrame
    """
    dfs = []
    
    for file_path in file_paths:
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            dfs.append(df)
            logger.info(f"Loaded {len(df)} records from {file_path}")
        else:
            logger.warning(f"File not found: {file_path}")
    
    if dfs:
        merged_df = pd.concat(dfs, ignore_index=True)
        merged_df.to_csv(output_path, index=False)
        logger.info(f"Merged {len(merged_df)} total records to {output_path}")
        return merged_df
    else:
        logger.error("No files to merge")
        return pd.DataFrame()


def calculate_load_statistics(df: pd.DataFrame, group_by: str = "ba_code") -> pd.DataFrame:
    """
    Calculate load statistics.
    
    Args:
        df: Load data DataFrame
        group_by: Column to group by
        
    Returns:
        DataFrame with statistics
    """
    stats = df.groupby(group_by)["load_mw"].agg([
        "count", "mean", "std", "min", "max",
        ("p25", lambda x: x.quantile(0.25)),
        ("p50", lambda x: x.quantile(0.50)),
        ("p75", lambda x: x.quantile(0.75)),
        ("p95", lambda x: x.quantile(0.95)),
        ("p99", lambda x: x.quantile(0.99))
    ]).round(2)
    
    return stats


def export_to_parquet(df: pd.DataFrame, output_path: str):
    """
    Export DataFrame to Parquet format.
    
    Args:
        df: DataFrame to export
        output_path: Output file path
    """
    df.to_parquet(output_path, index=False, compression="snappy")
    logger.info(f"Exported data to Parquet: {output_path}")


def load_and_validate_config(config_path: str) -> Dict:
    """
    Load and validate configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    import json
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Validate required fields
        required = ["balancing_authorities", "start_date", "end_date"]
        for field in required:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise


def format_memory_usage(df: pd.DataFrame) -> str:
    """
    Format DataFrame memory usage.
    
    Args:
        df: DataFrame
        
    Returns:
        Formatted memory usage string
    """
    memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    return f"{memory_mb:.2f} MB"


def create_summary_report(df: pd.DataFrame, output_path: str):
    """
    Create a summary report of the data.
    
    Args:
        df: Load data DataFrame
        output_path: Output file path
    """
    with open(output_path, "w") as f:
        f.write("EIA Load Data Summary Report\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Data Shape: {df.shape}\n")
        f.write(f"Memory Usage: {format_memory_usage(df)}\n")
        f.write(f"Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}\n")
        f.write(f"Balancing Authorities: {df['ba_code'].nunique()}\n\n")
        
        f.write("Load Statistics by BA:\n")
        f.write("-" * 30 + "\n")
        
        stats = calculate_load_statistics(df)
        f.write(stats.to_string())
        
    logger.info(f"Created summary report: {output_path}")