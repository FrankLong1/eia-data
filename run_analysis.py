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
from datetime import datetime
from pathlib import Path

# Import project modules
try:
    from src.download import EIADownloader
    from src.clean import clean_directory
    from src.analyze import CurtailmentAnalyzer
    from src.visualize import CurtailmentVisualizer
    import config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure all required modules are installed and accessible.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.PROJECT_ROOT / 'analysis.log')
    ]
)
logger = logging.getLogger(__name__)


def run_download_phase(bas=None, years=None, start_date=None, end_date=None, skip_existing=False):
    """Download BA aggregate demand data."""
    logger.info("Starting download phase...")
    
    # Use defaults if not specified
    bas = bas or config.BALANCING_AUTHORITIES
    
    if years:
        # Convert years to start/end dates
        start_date = f"{min(years)}-01-01"
        end_date = f"{max(years)}-12-31"
    else:
        start_date = start_date or config.DEFAULT_START_DATE
        end_date = end_date or config.DEFAULT_END_DATE
    
    logger.info(f"Downloading data for {len(bas)} BAs from {start_date} to {end_date}")
    
    try:
        downloader = EIADownloader()
        success_count = 0
        total_count = len(bas)
        
        for ba in bas:
            try:
                logger.info(f"Downloading data for {ba}...")
                result = downloader.download_ba_data(ba, start_date, end_date, skip_existing=skip_existing)
                if result is not None:
                    success_count += 1
                    logger.info(f"Successfully downloaded {len(result)} records for {ba}")
                else:
                    logger.warning(f"No data returned for {ba}")
            except Exception as e:
                logger.error(f"Failed to download data for {ba}: {e}")
                continue
        
        logger.info(f"Download phase completed: {success_count}/{total_count} BAs successful")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Download phase failed: {e}")
        return False


def run_cleaning_phase():
    """Clean and prepare downloaded data."""
    logger.info("Starting cleaning phase...")
    
    try:
        # Check for raw data files
        raw_files = list(config.RAW_DATA_DIR.glob("**/*.csv"))
        if not raw_files:
            logger.warning("No raw data files found. Skipping cleaning phase.")
            return True
        
        logger.info(f"Found {len(raw_files)} raw data files to clean")
        
        # Run cleaning process
        results = clean_directory(
            input_dir=str(config.RAW_DATA_DIR),
            output_dir=str(config.CLEANED_DATA_DIR)
        )
        
        success_count = sum(1 for r in results.values() if r)
        logger.info(f"Cleaning phase completed: {success_count}/{len(raw_files)} files cleaned successfully")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Cleaning phase failed: {e}")
        return False


def run_analysis_phase():
    """Perform curtailment analysis on cleaned data."""
    logger.info("Starting analysis phase...")
    
    try:
        # Check for cleaned data files
        cleaned_files = list(config.CLEANED_DATA_DIR.glob("*.csv"))
        if not cleaned_files:
            logger.warning("No cleaned data files found. Skipping analysis phase.")
            return True
        
        logger.info(f"Running curtailment analysis on {len(cleaned_files)} cleaned files")
        
        # Initialize analyzer
        analyzer = CurtailmentAnalyzer()
        
        # Run analysis for all curtailment rates
        results = analyzer.analyze_curtailment_headroom()
        
        if results is not None:
            logger.info(f"Analysis completed for {len(results)} BAs")
            
            # Save results
            results_file = config.RESULTS_DIR / "curtailment_analysis_results.csv"
            results.to_csv(results_file, index=False)
            logger.info(f"Results saved to {results_file}")
            
            return True
        else:
            logger.error("Analysis failed to produce results")
            return False
        
    except Exception as e:
        logger.error(f"Analysis phase failed: {e}")
        return False


def run_visualization_phase():
    """Create visualizations of analysis results."""
    logger.info("Starting visualization phase...")
    
    try:
        # Check for results
        results_file = config.RESULTS_DIR / "curtailment_analysis_results.csv"
        if not results_file.exists():
            logger.warning("No analysis results found. Skipping visualization phase.")
            return True
        
        logger.info("Creating visualizations...")
        
        # Initialize visualizer
        visualizer = CurtailmentVisualizer()
        
        # Create comprehensive report
        import pandas as pd
        results_df = pd.read_csv(results_file)
        plot_files = visualizer.create_comprehensive_report(results_df)
        
        logger.info(f"Visualization phase completed: {len(plot_files)} plots created")
        return True
        
    except Exception as e:
        logger.error(f"Visualization phase failed: {e}")
        return False


def run_full_pipeline(bas=None, years=None, start_date=None, end_date=None, skip_existing=False):
    """Run the complete analysis pipeline."""
    logger.info("Starting full analysis pipeline...")
    
    phases = [
        ("Download", lambda: run_download_phase(bas, years, start_date, end_date, skip_existing)),
        ("Cleaning", run_cleaning_phase),
        ("Analysis", run_analysis_phase),
        ("Visualization", run_visualization_phase)
    ]
    
    for phase_name, phase_func in phases:
        logger.info(f"Running {phase_name} phase...")
        if not phase_func():
            logger.error(f"{phase_name} phase failed. Stopping pipeline.")
            return False
    
    logger.info("Full pipeline completed successfully!")
    return True


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EIA curtailment analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline
  python run_analysis.py --full

  # Test with PJM data for 3 months
  python run_analysis.py --bas PJM --start 2023-10-01 --end 2023-12-31

  # Download specific BAs and years
  python run_analysis.py --download-only --bas PJM MISO --years 2022 2023

  # Analyze existing data
  python run_analysis.py --analyze-only
        """
    )
    
    # Pipeline modes
    parser.add_argument('--full', action='store_true',
                       help='Run complete pipeline (download, clean, analyze, visualize)')
    parser.add_argument('--download-only', action='store_true',
                       help='Download data only')
    parser.add_argument('--clean-only', action='store_true',
                       help='Clean existing data only')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Analyze existing cleaned data only')
    parser.add_argument('--visualize-only', action='store_true',
                       help='Create visualizations only')
    
    # Data selection
    parser.add_argument('--bas', type=str, nargs='+',
                       help='Specific BA codes to process')
    parser.add_argument('--years', type=int, nargs='+',
                       help='Years to process (e.g., --years 2022 2023)')
    parser.add_argument('--start', type=str,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true',
                       help='Process all 22 BAs for full date range')
    
    # Options
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip downloading files that already exist')
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_arguments()
    
    # Validate arguments
    if not any([args.full, args.download_only, args.clean_only, 
                args.analyze_only, args.visualize_only]):
        if args.bas or args.years or args.start or args.end or args.all:
            # If data selection args provided, assume full pipeline
            args.full = True
        else:
            print("Error: Must specify a pipeline mode (--full, --download-only, etc.)")
            print("Use --help for usage examples")
            return 1
    
    # Process BA selection
    bas = None
    if args.all:
        bas = config.BALANCING_AUTHORITIES
    elif args.bas:
        bas = args.bas
    
    # Run requested operations
    success = False
    
    if args.full:
        success = run_full_pipeline(bas, args.years, args.start, args.end, args.skip_existing)
    elif args.download_only:
        success = run_download_phase(bas, args.years, args.start, args.end, args.skip_existing)
    elif args.clean_only:
        success = run_cleaning_phase()
    elif args.analyze_only:
        success = run_analysis_phase()
    elif args.visualize_only:
        success = run_visualization_phase()
    
    if success:
        logger.info("Pipeline completed successfully!")
        return 0
    else:
        logger.error("Pipeline failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())