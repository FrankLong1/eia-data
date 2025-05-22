#!/usr/bin/env python
"""Main entry point for the EIA data pipeline."""

import argparse
import logging
import os
import sys
from datetime import datetime

from src.EIADataFetcher import EIADataFetcher
from src.data_cleaner import DataCleaner
from src.curtailment_analyzer import CurtailmentAnalyzer
from src.utils import setup_logging, validate_date_range, create_summary_report
from config import (
    BALANCING_AUTHORITIES, START_DATE, END_DATE,
    RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EIA Data Pipeline - Fetch, clean, and analyze hourly load data"
    )
    
    # Pipeline steps
    parser.add_argument(
        "--fetch", 
        action="store_true",
        help="Fetch data from EIA API"
    )
    parser.add_argument(
        "--clean", 
        action="store_true",
        help="Clean the fetched data"
    )
    parser.add_argument(
        "--analyze", 
        action="store_true",
        help="Analyze curtailment potential"
    )
    parser.add_argument(
        "--all", 
        action="store_true",
        help="Run complete pipeline (fetch, clean, analyze)"
    )
    
    # Data options
    parser.add_argument(
        "--ba-codes",
        nargs="+",
        default=BALANCING_AUTHORITIES,
        help="Balancing authority codes to process"
    )
    parser.add_argument(
        "--start-date",
        default=START_DATE,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        default=END_DATE,
        help="End date (YYYY-MM-DD)"
    )
    
    # Other options
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing data with latest values"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--api-key",
        help="EIA API key (can also be set as EIA_API_KEY env variable)"
    )
    
    return parser.parse_args()


def run_fetch_step(args):
    """Run the data fetching step."""
    logger = logging.getLogger(__name__)
    logger.info("Starting data fetch step")
    
    # Set API key if provided
    if args.api_key:
        os.environ["EIA_API_KEY"] = args.api_key
    
    # Initialize fetcher
    try:
        fetcher = EIADataFetcher()
    except ValueError as e:
        logger.error(f"Failed to initialize fetcher: {e}")
        return False
    
    # Fetch data
    if args.update:
        logger.info("Running in update mode")
        df = fetcher.update_data(args.ba_codes)
    else:
        logger.info(f"Fetching data from {args.start_date} to {args.end_date}")
        df = fetcher.fetch_all_ba_data(
            ba_codes=args.ba_codes,
            start_date=args.start_date,
            end_date=args.end_date
        )
    
    if df.empty:
        logger.error("No data fetched")
        return False
    
    logger.info(f"Successfully fetched {len(df)} records")
    return True


def run_clean_step(args):
    """Run the data cleaning step."""
    logger = logging.getLogger(__name__)
    logger.info("Starting data cleaning step")
    
    # Find the most recent raw data file
    raw_files = [f for f in os.listdir(RAW_DATA_DIR) if f.startswith("all_ba_hourly_load")]
    
    if not raw_files:
        logger.error("No raw data files found. Run fetch step first.")
        return False
    
    # Use the most recent file
    raw_files.sort()
    raw_file = raw_files[-1]
    raw_path = os.path.join(RAW_DATA_DIR, raw_file)
    
    logger.info(f"Loading raw data from {raw_path}")
    df = pd.read_csv(raw_path)
    
    # Clean data
    cleaner = DataCleaner()
    df_clean, quality_metrics = cleaner.clean_data(df)
    
    if df_clean.empty:
        logger.error("Cleaning resulted in empty dataset")
        return False
    
    logger.info(f"Successfully cleaned data. Shape: {df_clean.shape}")
    
    # Create summary report
    summary_path = os.path.join(PROCESSED_DATA_DIR, "data_summary_report.txt")
    create_summary_report(df_clean, summary_path)
    
    return True


def run_analyze_step(args):
    """Run the curtailment analysis step."""
    logger = logging.getLogger(__name__)
    logger.info("Starting curtailment analysis step")
    
    # Load cleaned data
    cleaned_path = os.path.join(PROCESSED_DATA_DIR, "cleaned_hourly_load_data.csv")
    
    if not os.path.exists(cleaned_path):
        logger.error("No cleaned data found. Run clean step first.")
        return False
    
    logger.info(f"Loading cleaned data from {cleaned_path}")
    df = pd.read_csv(cleaned_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Run analysis
    analyzer = CurtailmentAnalyzer()
    results = analyzer.analyze_curtailment_potential(df)
    
    # Generate report
    report = analyzer.generate_report(results)
    report_path = os.path.join(OUTPUT_DIR, "curtailment_analysis_report.txt")
    
    with open(report_path, "w") as f:
        f.write(report)
    
    logger.info(f"Analysis complete. Report saved to {report_path}")
    
    return True


def main():
    """Main pipeline function."""
    args = parse_arguments()
    
    # Set up logging
    log_file = f"eia_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    setup_logging(args.log_level, log_file)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting EIA data pipeline")
    
    # Validate date range
    if not validate_date_range(args.start_date, args.end_date):
        logger.error("Invalid date range")
        return 1
    
    # Determine which steps to run
    if args.all:
        steps = ["fetch", "clean", "analyze"]
    else:
        steps = []
        if args.fetch:
            steps.append("fetch")
        if args.clean:
            steps.append("clean")
        if args.analyze:
            steps.append("analyze")
    
    if not steps:
        logger.error("No steps specified. Use --fetch, --clean, --analyze, or --all")
        return 1
    
    # Import pandas here to avoid import errors if not needed
    if "clean" in steps or "analyze" in steps:
        global pd
        import pandas as pd
    
    # Run pipeline steps
    success = True
    
    if "fetch" in steps:
        success = run_fetch_step(args) and success
        if not success and not args.all:
            return 1
    
    if "clean" in steps:
        success = run_clean_step(args) and success
        if not success and not args.all:
            return 1
    
    if "analyze" in steps:
        success = run_analyze_step(args) and success
    
    if success:
        logger.info("Pipeline completed successfully")
        return 0
    else:
        logger.error("Pipeline completed with errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())