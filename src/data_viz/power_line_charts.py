"""
Power line chart visualization module for EIA electricity demand data.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PowerLineChartVisualizer:
    """Create line charts for power demand data from EIA."""
    
    def __init__(self, data_dir: str = "data/processed", output_dir: str = "data/visualizations"):
        """
        Initialize the visualizer.
        
        Args:
            data_dir: Directory containing processed CSV files
            output_dir: Directory to save chart images
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_ba_data(self, ba_code: str, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Load data for a specific balancing authority.
        
        Args:
            ba_code: Balancing authority code (e.g., 'CISO', 'PJM')
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            
        Returns:
            DataFrame with datetime index and demand values
        """
        # Look for CSV file in data directory
        csv_path = self.data_dir / f"{ba_code}_hourly_demand.csv"
        if not csv_path.exists():
            # Try raw data directory
            csv_path = self.data_dir.parent / "raw" / f"{ba_code}_hourly_demand.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(f"No data file found for {ba_code}")
        
        # Load data
        df = pd.read_csv(csv_path)
        
        # Convert period to datetime
        df['datetime'] = pd.to_datetime(df['period'])
        df = df.set_index('datetime')
        
        # Filter by date range if specified
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    def plot_single_ba(self, ba_code: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None, title: Optional[str] = None,
                       figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Create a line chart for a single balancing authority.
        
        Args:
            ba_code: Balancing authority code
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            title: Optional custom title
            figsize: Figure size (width, height)
            
        Returns:
            Matplotlib figure object
        """
        # Load data
        df = self.load_ba_data(ba_code, start_date, end_date)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot demand
        ax.plot(df.index, df['value'], label=f'{ba_code} Demand', linewidth=1.5)
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Demand (MW)', fontsize=12)
        ax.set_title(title or f'{ba_code} Hourly Electricity Demand', fontsize=14)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha='right')
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add legend
        ax.legend()
        
        # Tight layout
        plt.tight_layout()
        
        return fig
    
    def plot_multiple_bas(self, ba_codes: List[str], start_date: Optional[str] = None,
                          end_date: Optional[str] = None, title: Optional[str] = None,
                          figsize: Tuple[int, int] = (14, 8), 
                          normalize: bool = False) -> plt.Figure:
        """
        Create a line chart comparing multiple balancing authorities.
        
        Args:
            ba_codes: List of balancing authority codes
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            title: Optional custom title
            figsize: Figure size (width, height)
            normalize: If True, normalize all series to percentage of max
            
        Returns:
            Matplotlib figure object
        """
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot each BA
        for ba_code in ba_codes:
            try:
                df = self.load_ba_data(ba_code, start_date, end_date)
                
                if normalize:
                    # Normalize to percentage of max value
                    values = (df['value'] / df['value'].max()) * 100
                    ax.plot(df.index, values, label=ba_code, linewidth=1.5)
                else:
                    ax.plot(df.index, df['value'], label=ba_code, linewidth=1.5)
                    
            except FileNotFoundError:
                logger.warning(f"No data found for {ba_code}, skipping")
                continue
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Demand (%)' if normalize else 'Demand (MW)', fontsize=12)
        ax.set_title(title or 'Hourly Electricity Demand Comparison', fontsize=14)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha='right')
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add legend
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Tight layout
        plt.tight_layout()
        
        return fig
    
    def plot_daily_profile(self, ba_code: str, date: str, 
                          figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Plot 24-hour demand profile for a specific date.
        
        Args:
            ba_code: Balancing authority code
            date: Date to plot (YYYY-MM-DD)
            figsize: Figure size (width, height)
            
        Returns:
            Matplotlib figure object
        """
        # Load data for the specific date
        df = self.load_ba_data(ba_code, date, date)
        
        # Extract hour from datetime
        df['hour'] = df.index.hour
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot hourly demand
        ax.plot(df['hour'], df['value'], marker='o', linewidth=2, markersize=6)
        
        # Formatting
        ax.set_xlabel('Hour of Day', fontsize=12)
        ax.set_ylabel('Demand (MW)', fontsize=12)
        ax.set_title(f'{ba_code} Daily Demand Profile - {date}', fontsize=14)
        ax.set_xticks(range(0, 24))
        ax.grid(True, alpha=0.3)
        
        # Tight layout
        plt.tight_layout()
        
        return fig
    
    def save_chart(self, fig: plt.Figure, filename: str, dpi: int = 300) -> Path:
        """
        Save a chart to file.
        
        Args:
            fig: Matplotlib figure object
            filename: Output filename (without extension)
            dpi: Resolution in dots per inch
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / f"{filename}.png"
        fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
        logger.info(f"Chart saved to {output_path}")
        return output_path
    
    def create_ba_summary_chart(self, ba_code: str, year: int) -> Path:
        """
        Create a summary chart for a BA showing full year of data.
        
        Args:
            ba_code: Balancing authority code
            year: Year to visualize
            
        Returns:
            Path to saved chart
        """
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        fig = self.plot_single_ba(ba_code, start_date, end_date,
                                  title=f"{ba_code} Electricity Demand - {year}")
        
        output_path = self.save_chart(fig, f"{ba_code}_{year}_summary")
        plt.close(fig)
        
        return output_path


def main():
    """Example usage of the power line chart visualizer."""
    # Setup basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create visualizer
    viz = PowerLineChartVisualizer()
    
    # Example 1: Single BA chart
    try:
        fig = viz.plot_single_ba('CISO', '2024-01-01', '2024-01-31')
        viz.save_chart(fig, 'CISO_january_2024')
        plt.close(fig)
    except FileNotFoundError:
        logger.info("CISO data not found, skipping example 1")
    
    # Example 2: Multiple BAs comparison
    try:
        fig = viz.plot_multiple_bas(['CISO', 'PJM', 'ERCO'], 
                                   '2024-01-01', '2024-01-07',
                                   normalize=True)
        viz.save_chart(fig, 'multi_ba_comparison_normalized')
        plt.close(fig)
    except Exception as e:
        logger.info(f"Multi-BA comparison failed: {e}")
    
    # Example 3: Daily profile
    try:
        fig = viz.plot_daily_profile('PJM', '2024-01-15')
        viz.save_chart(fig, 'PJM_daily_profile_example')
        plt.close(fig)
    except FileNotFoundError:
        logger.info("PJM data not found, skipping example 3")
    
    logger.info("Visualization examples complete")


if __name__ == "__main__":
    main()