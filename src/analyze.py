#!/usr/bin/env python3
"""
Simplified curtailment analysis module for EIA data project.

This module implements curtailment-enabled headroom analysis based on methodology from 
"Rethinking Load Growth" paper by Norris et al. (2025). It calculates the maximum 
constant load that can be added to each balancing authority while staying within 
specified curtailment limits.

Key functionality:
- Curtailment-enabled headroom calculation for standard rates (0.25%, 0.5%, 1.0%, 5.0%)
- Seasonal peak threshold analysis (summer vs winter)
- Load factor calculations
- Curtailment duration and pattern analysis
- Simple API for analyzing individual BA files or batch processing

Usage:
    analyzer = CurtailmentAnalyzer(cleaned_data_df)
    results = analyzer.analyze_curtailment_headroom()
    
    # Or analyze individual BA
    headroom = analyzer.calculate_headroom_for_ba('PJM', curtailment_limit=0.005)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.optimize import root_scalar
import logging
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Standard curtailment rates from the paper
STANDARD_CURTAILMENT_RATES = [0.0025, 0.005, 0.01, 0.05]  # 0.25%, 0.5%, 1.0%, 5.0%

# Seasonal month definitions
SUMMER_MONTHS = [6, 7, 8]  # June-August
WINTER_MONTHS = [12, 1, 2]  # December-February
SHOULDER_MONTHS = {
    'summer': [4, 5, 9, 10],  # April-May, September-October use summer peak
    'winter': [11, 3]  # November, March use winter peak
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class CurtailmentAnalyzer:
    """
    Analyzes curtailment-enabled headroom for balancing authorities.
    
    This class implements the methodology from Norris et al. (2025) to determine
    how much new constant load can be added to each BA while keeping curtailment
    of that new load within specified limits.
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the analyzer with cleaned BA data.
        
        Args:
            data: DataFrame with columns:
                  - Timestamp: datetime
                  - Balancing Authority: BA name
                  - Unified Demand: demand in MW
        """
        self.data = data.copy()
        self.seasonal_peaks = {}
        self.load_factors = {}
        
        # Ensure proper datetime format
        if 'Timestamp' in self.data.columns:
            self.data['Timestamp'] = pd.to_datetime(self.data['Timestamp'])
        
        # Validate required columns
        required_columns = ['Timestamp', 'Balancing Authority', 'Unified Demand']
        missing_cols = [col for col in required_columns if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Remove any rows with missing critical data
        self.data = self.data.dropna(subset=['Timestamp', 'Balancing Authority', 'Unified Demand'])
        
        # Calculate seasonal peaks and load factors for all BAs
        self._calculate_seasonal_peaks()
        self._calculate_load_factors()
        
        logging.info(f"Initialized analyzer with {len(self.data):,} data points for {len(self.get_available_bas())} BAs")
    
    def get_available_bas(self) -> List[str]:
        """Get list of available balancing authorities in the dataset."""
        return sorted(self.data['Balancing Authority'].unique())
    
    def _calculate_seasonal_peaks(self) -> None:
        """Calculate seasonal peak thresholds for all BAs."""
        for ba in self.get_available_bas():
            ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
            if ba_data.empty:
                continue
                
            ba_data['Month'] = ba_data['Timestamp'].dt.month
            
            # Calculate seasonal peaks
            summer_data = ba_data[ba_data['Month'].isin(SUMMER_MONTHS)]
            winter_data = ba_data[ba_data['Month'].isin(WINTER_MONTHS)]
            
            summer_peak = summer_data['Unified Demand'].max() if not summer_data.empty else 0
            winter_peak = winter_data['Unified Demand'].max() if not winter_data.empty else 0
            
            # Handle edge cases where seasonal data might be missing
            if summer_peak == 0 and winter_peak == 0:
                overall_peak = ba_data['Unified Demand'].max()
                summer_peak = winter_peak = overall_peak
            elif summer_peak == 0:
                summer_peak = winter_peak
            elif winter_peak == 0:
                winter_peak = summer_peak
            
            self.seasonal_peaks[ba] = {
                'summer': summer_peak,
                'winter': winter_peak
            }
    
    def _calculate_load_factors(self) -> None:
        """Calculate load factors for all BAs."""
        for ba in self.get_available_bas():
            ba_data = self.data[self.data['Balancing Authority'] == ba]
            if ba_data.empty:
                continue
                
            avg_demand = ba_data['Unified Demand'].mean()
            peak_demand = ba_data['Unified Demand'].max()
            
            load_factor = avg_demand / peak_demand if peak_demand > 0 else 0
            self.load_factors[ba] = load_factor
    
    def _get_seasonal_threshold(self, timestamp: pd.Timestamp, ba: str) -> float:
        """
        Get applicable seasonal peak threshold for a given timestamp.
        
        Args:
            timestamp: Hour to check
            ba: Balancing authority
            
        Returns:
            Seasonal peak threshold in MW
        """
        month = timestamp.month
        
        # Primary seasons
        if month in SUMMER_MONTHS:
            return self.seasonal_peaks[ba]['summer']
        elif month in WINTER_MONTHS:
            return self.seasonal_peaks[ba]['winter']
        # Shoulder months
        elif month in SHOULDER_MONTHS['summer']:
            return self.seasonal_peaks[ba]['summer']
        elif month in SHOULDER_MONTHS['winter']:
            return self.seasonal_peaks[ba]['winter']
        else:
            # Fallback to maximum of both seasons
            return max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
    
    def calculate_curtailment_rate(self, ba: str, load_addition: float) -> Optional[float]:
        """
        Calculate curtailment rate for a given load addition.
        
        Args:
            ba: Balancing authority name
            load_addition: Constant load to add (MW)
            
        Returns:
            Curtailment rate (fraction between 0 and 1)
        """
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty or ba not in self.seasonal_peaks:
            return None
        
        # Add new load to existing demand
        ba_data['Augmented_Demand'] = ba_data['Unified Demand'] + load_addition
        
        # Get seasonal threshold for each hour
        ba_data['Seasonal_Threshold'] = ba_data['Timestamp'].apply(
            lambda x: self._get_seasonal_threshold(x, ba)
        )
        
        # Calculate required curtailment
        ba_data['Curtailment'] = np.maximum(0, ba_data['Augmented_Demand'] - ba_data['Seasonal_Threshold'])
        
        # Calculate curtailment rate
        total_added_energy = load_addition * len(ba_data)
        total_curtailed_energy = ba_data['Curtailment'].sum()
        
        if total_added_energy <= 0:
            return 0.0
        
        return total_curtailed_energy / total_added_energy
    
    def calculate_detailed_curtailment_metrics(self, ba: str, load_addition: float) -> Dict:
        """
        Calculate detailed curtailment metrics for a load addition.
        
        Args:
            ba: Balancing authority
            load_addition: Constant load addition in MW
            
        Returns:
            Dictionary with comprehensive curtailment metrics
        """
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty or ba not in self.seasonal_peaks:
            return {}
        
        # Add new load and calculate curtailment
        ba_data['Augmented_Demand'] = ba_data['Unified Demand'] + load_addition
        ba_data['Seasonal_Threshold'] = ba_data['Timestamp'].apply(
            lambda x: self._get_seasonal_threshold(x, ba)
        )
        ba_data['Curtailment'] = np.maximum(0, ba_data['Augmented_Demand'] - ba_data['Seasonal_Threshold'])
        ba_data['Is_Curtailed'] = ba_data['Curtailment'] > 0
        
        # Basic metrics
        total_curtailment_mwh = ba_data['Curtailment'].sum()
        max_potential_mwh = load_addition * len(ba_data)
        curtailment_rate = total_curtailment_mwh / max_potential_mwh if max_potential_mwh > 0 else 0
        
        # Curtailment hours and duration
        curtailed_hours = ba_data[ba_data['Is_Curtailed']]
        num_curtailed_hours = len(curtailed_hours)
        
        # Calculate consecutive curtailment events
        if num_curtailed_hours > 0:
            ba_data['Event_Group'] = (ba_data['Is_Curtailed'] != ba_data['Is_Curtailed'].shift()).cumsum()
            curtailment_events = ba_data[ba_data['Is_Curtailed']].groupby('Event_Group').size()
            avg_duration = curtailment_events.mean()
            max_duration = curtailment_events.max()
            
            # Load retention during curtailment
            avg_curtailment_depth = curtailed_hours['Curtailment'].mean() / load_addition
            avg_load_retention = 1 - avg_curtailment_depth
            
            # Seasonal analysis
            curtailed_hours_with_season = curtailed_hours.copy()
            curtailed_hours_with_season['Month'] = curtailed_hours_with_season['Timestamp'].dt.month
            curtailed_hours_with_season['Season'] = curtailed_hours_with_season['Month'].apply(
                lambda m: 'summer' if m in SUMMER_MONTHS + SHOULDER_MONTHS['summer'] else 'winter'
            )
            seasonal_breakdown = curtailed_hours_with_season.groupby('Season').size().to_dict()
            
        else:
            avg_duration = 0
            max_duration = 0
            avg_load_retention = 1.0
            seasonal_breakdown = {'summer': 0, 'winter': 0}
        
        return {
            'ba': ba,
            'load_addition_mw': load_addition,
            'load_addition_gw': load_addition / 1000,
            'curtailment_rate': curtailment_rate,
            'curtailment_rate_pct': curtailment_rate * 100,
            'total_curtailment_mwh': total_curtailment_mwh,
            'curtailed_hours_per_year': num_curtailed_hours,
            'avg_duration_hours': avg_duration,
            'max_duration_hours': max_duration,
            'avg_load_retention': avg_load_retention,
            'avg_load_retention_pct': avg_load_retention * 100,
            'seasonal_curtailment': seasonal_breakdown,
            'load_factor': self.load_factors.get(ba, 0),
            'summer_peak_mw': self.seasonal_peaks[ba]['summer'],
            'winter_peak_mw': self.seasonal_peaks[ba]['winter']
        }
    
    def find_headroom_for_curtailment_limit(self, ba: str, target_curtailment_rate: float,
                                          tolerance: float = 1e-6) -> Optional[float]:
        """
        Find maximum load addition that achieves target curtailment rate.
        
        Args:
            ba: Balancing authority
            target_curtailment_rate: Target curtailment rate (e.g., 0.005 for 0.5%)
            tolerance: Convergence tolerance
            
        Returns:
            Maximum load addition in MW
        """
        if ba not in self.seasonal_peaks:
            logging.warning(f"No seasonal peak data for BA: {ba}")
            return None
        
        def objective(load_addition):
            """Objective function for root finding."""
            curtailment_rate = self.calculate_curtailment_rate(ba, load_addition)
            if curtailment_rate is None:
                return float('inf')
            return curtailment_rate - target_curtailment_rate
        
        # Set bounds based on peak demand
        peak_demand = max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
        lower_bound = 0
        upper_bound = peak_demand * 0.5  # Start with 50% of peak
        
        # Expand upper bound if needed
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            try:
                obj_upper = objective(upper_bound)
                if obj_upper > 0:  # Found valid upper bound
                    break
                upper_bound *= 2
                iteration += 1
            except:
                upper_bound *= 2
                iteration += 1
        
        if iteration >= max_iterations:
            logging.warning(f"Could not find valid bounds for {ba}")
            return None
        
        try:
            # Use root-finding to solve for exact load addition
            result = root_scalar(objective, bracket=[lower_bound, upper_bound], 
                               method='brentq', xtol=tolerance)
            return result.root
        except Exception as e:
            logging.error(f"Root finding failed for {ba}: {e}")
            return None
    
    def calculate_headroom_for_ba(self, ba: str, curtailment_limits: List[float] = None) -> pd.DataFrame:
        """
        Calculate curtailment-enabled headroom for a single BA.
        
        Args:
            ba: Balancing authority
            curtailment_limits: List of curtailment limits to analyze
            
        Returns:
            DataFrame with headroom results
        """
        if curtailment_limits is None:
            curtailment_limits = STANDARD_CURTAILMENT_RATES
        
        results = []
        
        for limit in curtailment_limits:
            max_load = self.find_headroom_for_curtailment_limit(ba, limit)
            
            if max_load is not None:
                metrics = self.calculate_detailed_curtailment_metrics(ba, max_load)
                results.append(metrics)
        
        return pd.DataFrame(results)
    
    def analyze_curtailment_headroom(self, ba_list: List[str] = None, 
                                   curtailment_limits: List[float] = None) -> pd.DataFrame:
        """
        Analyze curtailment-enabled headroom for multiple BAs.
        
        Args:
            ba_list: List of BAs to analyze (None for all available)
            curtailment_limits: List of curtailment limits to analyze
            
        Returns:
            DataFrame with comprehensive headroom analysis
        """
        if ba_list is None:
            ba_list = self.get_available_bas()
        
        if curtailment_limits is None:
            curtailment_limits = STANDARD_CURTAILMENT_RATES
        
        all_results = []
        
        for ba in ba_list:
            logging.info(f"Analyzing curtailment headroom for {ba}...")
            
            ba_results = self.calculate_headroom_for_ba(ba, curtailment_limits)
            if not ba_results.empty:
                all_results.append(ba_results)
        
        if not all_results:
            return pd.DataFrame()
        
        combined_results = pd.concat(all_results, ignore_index=True)
        
        # Sort by BA and curtailment rate
        combined_results = combined_results.sort_values(['ba', 'curtailment_rate'])
        
        return combined_results
    
    def create_curtailment_curve(self, ba: str, max_load_pct: float = 0.3, 
                               num_points: int = 50) -> pd.DataFrame:
        """
        Create curtailment curve showing relationship between load addition and curtailment.
        
        Args:
            ba: Balancing authority
            max_load_pct: Maximum load addition as percentage of peak
            num_points: Number of points to calculate
            
        Returns:
            DataFrame with load additions and curtailment rates
        """
        if ba not in self.seasonal_peaks:
            return pd.DataFrame()
        
        peak_demand = max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
        max_load = peak_demand * max_load_pct
        
        load_additions = np.linspace(0, max_load, num_points)
        results = []
        
        for load_addition in load_additions:
            curtailment_rate = self.calculate_curtailment_rate(ba, load_addition)
            if curtailment_rate is not None:
                results.append({
                    'ba': ba,
                    'load_addition_mw': load_addition,
                    'load_addition_gw': load_addition / 1000,
                    'load_addition_pct_of_peak': (load_addition / peak_demand) * 100,
                    'curtailment_rate': curtailment_rate,
                    'curtailment_rate_pct': curtailment_rate * 100
                })
        
        return pd.DataFrame(results)
    
    def get_ba_summary(self, ba: str) -> Dict:
        """
        Get summary statistics for a balancing authority.
        
        Args:
            ba: Balancing authority
            
        Returns:
            Dictionary with BA summary statistics
        """
        ba_data = self.data[self.data['Balancing Authority'] == ba]
        
        if ba_data.empty or ba not in self.seasonal_peaks:
            return {}
        
        return {
            'ba': ba,
            'data_points': len(ba_data),
            'start_date': ba_data['Timestamp'].min().strftime('%Y-%m-%d'),
            'end_date': ba_data['Timestamp'].max().strftime('%Y-%m-%d'),
            'summer_peak_mw': self.seasonal_peaks[ba]['summer'],
            'winter_peak_mw': self.seasonal_peaks[ba]['winter'],
            'load_factor': self.load_factors.get(ba, 0),
            'avg_demand_mw': ba_data['Unified Demand'].mean(),
            'min_demand_mw': ba_data['Unified Demand'].min(),
            'max_demand_mw': ba_data['Unified Demand'].max()
        }
    
    def analyze_seasonal_patterns(self, ba: str) -> Dict:
        """
        Analyze seasonal demand patterns for a BA.
        
        Args:
            ba: Balancing authority
            
        Returns:
            Dictionary with seasonal analysis
        """
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty:
            return {}
        
        ba_data['Month'] = ba_data['Timestamp'].dt.month
        ba_data['Season'] = ba_data['Month'].apply(
            lambda m: 'summer' if m in SUMMER_MONTHS + SHOULDER_MONTHS['summer'] else 'winter'
        )
        
        seasonal_stats = ba_data.groupby('Season')['Unified Demand'].agg([
            'mean', 'max', 'min', 'std'
        ]).round(1)
        
        return {
            'ba': ba,
            'seasonal_stats': seasonal_stats.to_dict(),
            'summer_winter_peak_ratio': (self.seasonal_peaks[ba]['summer'] / 
                                       self.seasonal_peaks[ba]['winter'] 
                                       if self.seasonal_peaks[ba]['winter'] > 0 else 0),
            'load_factor': self.load_factors.get(ba, 0)
        }


def load_cleaned_data(data_dir: Union[str, Path]) -> pd.DataFrame:
    """
    Load cleaned BA data from directory structure.
    
    Args:
        data_dir: Path to directory containing cleaned data
        
    Returns:
        Combined DataFrame with all BA data
    """
    data_dir = Path(data_dir)
    all_data = []
    
    if data_dir.exists():
        for file_path in data_dir.glob("**/*.csv"):
            try:
                df = pd.read_csv(file_path)
                if 'Timestamp' in df.columns:
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                all_data.append(df)
            except Exception as e:
                logging.warning(f"Error loading {file_path}: {e}")
    
    if not all_data:
        raise ValueError(f"No data found in {data_dir}")
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Remove duplicates
    combined_df = combined_df.drop_duplicates(subset=['Timestamp', 'Balancing Authority'], keep='first')
    
    logging.info(f"Loaded {len(combined_df):,} data points from {len(all_data)} files")
    
    return combined_df


def main():
    """Example usage of the curtailment analyzer."""
    
    # Try to load data from expected locations
    possible_data_dirs = [
        "/Users/franklong/Projects/eia-data/data/cleaned",
        "/Users/franklong/Projects/eia-data/ba_aggregate_data/cleaned",
        "./data/cleaned"
    ]
    
    data_df = None
    for data_dir in possible_data_dirs:
        try:
            data_df = load_cleaned_data(data_dir)
            logging.info(f"Successfully loaded data from {data_dir}")
            break
        except:
            continue
    
    if data_df is None:
        logging.error("Could not find cleaned data. Please run data cleaning first.")
        return
    
    # Initialize analyzer
    analyzer = CurtailmentAnalyzer(data_df)
    
    # Analyze top BAs by average demand
    avg_demand_by_ba = data_df.groupby('Balancing Authority')['Unified Demand'].mean().sort_values(ascending=False)
    top_bas = avg_demand_by_ba.head(10).index.tolist()
    
    logging.info(f"Analyzing top {len(top_bas)} BAs by demand: {top_bas}")
    
    # Run comprehensive analysis
    results = analyzer.analyze_curtailment_headroom(top_bas)
    
    if not results.empty:
        # Display results
        print("\n" + "="*80)
        print("CURTAILMENT-ENABLED HEADROOM ANALYSIS")
        print("="*80)
        
        display_cols = ['ba', 'curtailment_rate_pct', 'load_addition_gw', 
                       'curtailed_hours_per_year', 'avg_duration_hours', 
                       'avg_load_retention_pct', 'load_factor']
        
        print(results[display_cols].to_string(index=False, float_format='%.2f'))
        
        # Create output directory
        output_dir = Path("./data/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save results
        results.to_csv(output_dir / "curtailment_headroom_analysis.csv", index=False)
        print(f"\nDetailed results saved to {output_dir}/curtailment_headroom_analysis.csv")
        
        # Save BA summaries
        summaries = []
        for ba in top_bas:
            summary = analyzer.get_ba_summary(ba)
            if summary:
                summaries.append(summary)
        
        if summaries:
            summary_df = pd.DataFrame(summaries)
            summary_df.to_csv(output_dir / "ba_summaries.csv", index=False)
            print(f"BA summaries saved to {output_dir}/ba_summaries.csv")
    
    else:
        print("No results generated. Please check data quality and try again.")


if __name__ == "__main__":
    main()