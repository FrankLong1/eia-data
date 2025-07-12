#!/usr/bin/env python3
"""
Main script for EIA curtailment analysis pipeline.
Implements the methodology from "Rethinking Load Growth" (Norris et al., 2025)

Usage:
    python run_analysis.py --full                    # Run complete pipeline
    python run_analysis.py --download-only           # Download data only
    python run_analysis.py --analyze-only            # Analyze existing data
    python run_analysis.py --bas PJM MISO --years 2022 2023  # Custom subset
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd

from src.download import download_all_ba_data
from src.clean import clean_data_directory
from src.analyze import CurtailmentAnalyzer
from src.visualize import CurtailmentVisualizer
import config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def load_combined_data(data_dir):
    """Load and combine all CSV files from a directory."""
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    
    files = list(data_path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    all_data = []
    for file_path in files:
        df = pd.read_csv(file_path)
        all_data.append(df)
    
    return pd.concat(all_data, ignore_index=True)


def run_download_phase(bas=None, start_date=None, end_date=None, skip_existing=False):
    """Download BA aggregate demand data."""
    logging.info("Starting download phase...")
    
    bas = bas or config.BALANCING_AUTHORITIES
    start_date = start_date or config.DEFAULT_START_DATE
    end_date = end_date or config.DEFAULT_END_DATE
    
    logging.info(f"Downloading data for {len(bas)} BAs from {start_date} to {end_date}")
    
    # Ensure output directory exists
    Path(config.RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
    
    download_all_ba_data(bas, start_date, end_date, str(config.RAW_DATA_DIR), skip_existing)
    
    logging.info("Download phase completed")


def run_cleaning_phase():
    """Clean and prepare downloaded data."""
    logging.info("Starting cleaning phase...")
    
    raw_data_path = Path(config.RAW_DATA_DIR)
    raw_data_path.mkdir(parents=True, exist_ok=True)
    
    raw_files = list(raw_data_path.glob("**/*.csv"))
    if not raw_files:
        raise FileNotFoundError("No raw data files found - make sure the download phase completed successfully")
    
    logging.info(f"Cleaning {len(raw_files)} files")
    
    # Ensure output directory exists
    Path(config.CLEANED_DATA_DIR).mkdir(parents=True, exist_ok=True)
    
    results = clean_data_directory(str(config.RAW_DATA_DIR), str(config.CLEANED_DATA_DIR))
    
    success_count = sum(1 for r in results.values() if r is not None and not r.empty)
    logging.info(f"Cleaned {success_count}/{len(raw_files)} files successfully")


def run_analysis_phase():
    """Perform curtailment analysis on cleaned data."""
    logging.info("Starting analysis phase...")
    
    combined_data = load_combined_data(config.CLEANED_DATA_DIR)
    logging.info(f"Loaded {len(combined_data)} records for analysis")
    
    analyzer = CurtailmentAnalyzer(combined_data)
    results = analyzer.analyze_curtailment_headroom()
    
    if results is None:
        raise RuntimeError("Analysis failed to produce results")
    
    # Save results
    results_path = Path(config.RESULTS_DIR)
    results_path.mkdir(parents=True, exist_ok=True)
    results_file = results_path / "curtailment_analysis_results.csv"
    results.to_csv(results_file, index=False)
    
    logging.info(f"Analysis completed for {len(results)} BAs, saved to {results_file}")


def run_visualization_phase():
    """Create visualizations of analysis results."""
    logging.info("Starting visualization phase...")
    
    results_file = Path(config.RESULTS_DIR) / "curtailment_analysis_results.csv"
    if not results_file.exists():
        raise FileNotFoundError("No analysis results found - run analysis phase first")
    
    results_df = pd.read_csv(results_file)
    
    # Load BA data for visualizations
    ba_data_dict = {}
    for file_path in Path(config.CLEANED_DATA_DIR).glob("*.csv"):
        df = pd.read_csv(file_path)
        ba_name = (df['Balancing Authority'].iloc[0] if 'Balancing Authority' in df.columns 
                   else file_path.stem.split('_')[1])
        ba_data_dict[ba_name] = df
    
    logging.info(f"Creating visualizations for {len(ba_data_dict)} BAs")
    
    visualizer = CurtailmentVisualizer()
    plot_files = visualizer.create_comprehensive_report(results_df, ba_data_dict)
    
    logging.info(f"Created {len(plot_files)} visualizations")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EIA curtailment analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline (default)
  python run_analysis.py

  # Test with PJM data for 3 months
  python run_analysis.py --bas PJM --start 10-01-2023 --end 12-31-2023

  # Force re-download of existing files
  python run_analysis.py --redownload

  # Process specific BAs and date range
  python run_analysis.py --bas PJM MISO --start 01-01-2022 --end 12-31-2023
        """
    )
    
    # Data selection
    parser.add_argument('--bas', type=str, nargs='+',
                       help='Specific BA codes to process')
    parser.add_argument('--start', type=str,
                       help='Start date (MM-DD-YYYY)')
    parser.add_argument('--end', type=str,
                       help='End date (MM-DD-YYYY)')
    parser.add_argument('--all', action='store_true',
                       help='Process all 22 BAs for full date range')
    
    # Options
    parser.add_argument('--redownload', action='store_true',
                       help='Force re-download of files even if they already exist')
    
    return parser.parse_args()


def convert_date_format(date_str):
    """Convert MM-DD-YYYY to YYYY-MM-DD format."""
    if not date_str:
        return date_str
    month, day, year = date_str.split('-')
    return f"{year}-{month}-{day}"


def main():
    """Main function."""
    args = parse_arguments()
    
    # Convert date formats
    start_date = convert_date_format(args.start)
    end_date = convert_date_format(args.end)
    
    # Process BA selection
    bas = config.BALANCING_AUTHORITIES if args.all else args.bas
    skip_existing = not args.redownload
    
    # Run full pipeline
    run_download_phase(bas, start_date, end_date, skip_existing)
    run_cleaning_phase()
    run_analysis_phase()
    run_visualization_phase()
    
    logging.info("Pipeline completed successfully!")


if __name__ == "__main__":
    sys.exit(main())