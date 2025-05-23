#!/usr/bin/env python3
"""
Curtailment analysis for flexible load integration in US power systems.

Based on methodology from "Rethinking Load Growth" paper by Norris et al. (2025).
Calculates the maximum new constant load that can be added to each balancing authority
while staying within specified curtailment limits.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.optimize import root_scalar
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class CurtailmentAnalyzer:
    """
    Analyzes curtailment-enabled headroom for balancing authorities.
    
    The analysis determines how much new constant load can be added to each BA
    while keeping curtailment of that new load within specified limits.
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the analyzer with a DataFrame.
        
        Args:
            data: DataFrame containing cleaned BA data with columns:
                  - Timestamp: datetime
                  - Balancing Authority: BA name
                  - Unified Demand: demand in MW
        """
        self.data = data
        self.ba_data = {}
        self.seasonal_peaks = {}
        
        # Ensure Timestamp is datetime
        if 'Timestamp' in self.data.columns:
            self.data['Timestamp'] = pd.to_datetime(self.data['Timestamp'])
        
    def load_ba_data(self, ba_list: Optional[List[str]] = None) -> None:
        """
        Load cleaned data for specified BAs or all available BAs.
        
        Args:
            ba_list: List of BA codes to load, or None to load all
        """
        if ba_list is None:
            # Get all BA directories
            ba_dirs = [d for d in self.data_dir.iterdir() if d.is_dir()]
            ba_list = [d.name for d in ba_dirs]
            
        for ba in ba_list:
            ba_dir = self.data_dir / ba
            if not ba_dir.exists():
                logging.warning(f"BA directory not found: {ba}")
                continue
                
            # Load all years of data for this BA
            all_data = []
            for csv_file in sorted(ba_dir.glob("*.csv")):
                try:
                    df = pd.read_csv(csv_file)
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                    all_data.append(df)
                except Exception as e:
                    logging.error(f"Error loading {csv_file}: {e}")
                    
            if all_data:
                # Combine all years
                ba_df = pd.concat(all_data, ignore_index=True)
                ba_df = ba_df.sort_values('Timestamp')
                self.ba_data[ba] = ba_df
                logging.info(f"Loaded {len(ba_df)} hours of data for {ba}")
                
    def calculate_seasonal_peak(self, ba: str, season: str) -> Optional[float]:
        """
        Calculate the seasonal peak demand for a specific BA and season.
        
        Args:
            ba: Balancing authority name
            season: 'summer' or 'winter'
            
        Returns:
            Peak demand in MW or None if no data
        """
        # Filter data for this BA
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty:
            logging.warning(f"No data found for BA: {ba}")
            return None
            
        # Extract month
        ba_data['Month'] = ba_data['Timestamp'].dt.month
        
        # Define seasons
        if season == 'summer':
            season_months = [6, 7, 8]  # June-August
        elif season == 'winter':
            season_months = [12, 1, 2]  # December-February
        else:
            raise ValueError(f"Invalid season: {season}")
            
        # Filter for season
        season_data = ba_data[ba_data['Month'].isin(season_months)]
        
        if season_data.empty:
            logging.warning(f"No {season} data found for BA: {ba}")
            return None
            
        return season_data['Unified Demand'].max()
    
    def calculate_seasonal_peaks(self) -> None:
        """
        Calculate maximum seasonal peaks for each BA across all years.
        
        Summer: June-August
        Winter: December-February
        """
        for ba, df in self.ba_data.items():
            # Extract month from timestamp
            df['Month'] = df['Timestamp'].dt.month
            
            # Define seasons
            summer_months = [6, 7, 8]  # June-August
            winter_months = [12, 1, 2]  # December-February
            
            # Calculate seasonal peaks
            summer_data = df[df['Month'].isin(summer_months)]
            winter_data = df[df['Month'].isin(winter_months)]
            
            summer_peak = summer_data['Unified Demand'].max() if not summer_data.empty else 0
            winter_peak = winter_data['Unified Demand'].max() if not winter_data.empty else 0
            
            self.seasonal_peaks[ba] = {
                'summer': summer_peak,
                'winter': winter_peak
            }
            
            logging.info(f"{ba} - Summer peak: {summer_peak:.0f} MW, Winter peak: {winter_peak:.0f} MW")
            
    def get_seasonal_threshold(self, timestamp: pd.Timestamp, ba: str) -> float:
        """
        Get the applicable seasonal peak threshold for a given hour.
        
        Args:
            timestamp: Hour to check
            ba: Balancing authority code
            
        Returns:
            Seasonal peak threshold in MW
        """
        month = timestamp.month
        
        # Summer months: April-October
        if 4 <= month <= 10:
            return self.seasonal_peaks[ba]['summer']
        # Winter months: November-March
        else:
            return self.seasonal_peaks[ba]['winter']
            
    def calculate_curtailment(self, ba: str, load_addition: float) -> Dict[str, float]:
        """
        Calculate curtailment metrics for a given load addition.
        
        Args:
            ba: Balancing authority code
            load_addition: Constant load addition in MW
            
        Returns:
            Dictionary with curtailment metrics
        """
        df = self.ba_data[ba].copy()
        
        # Add new load to existing demand
        df['Augmented Demand'] = df['Unified Demand'] + load_addition
        
        # Get seasonal threshold for each hour
        df['Threshold'] = df['Timestamp'].apply(lambda x: self.get_seasonal_threshold(x, ba))
        
        # Calculate hourly curtailment (only when augmented demand exceeds threshold)
        df['Curtailment'] = np.maximum(0, df['Augmented Demand'] - df['Threshold'])
        
        # Calculate metrics
        total_curtailment_mwh = df['Curtailment'].sum()
        max_potential_mwh = load_addition * len(df)  # Assuming 1 hour per row
        curtailment_rate = total_curtailment_mwh / max_potential_mwh if max_potential_mwh > 0 else 0
        
        # Hours with curtailment
        curtailed_hours = df[df['Curtailment'] > 0]
        num_curtailed_hours = len(curtailed_hours)
        
        # Average curtailment duration (consecutive hours)
        if num_curtailed_hours > 0:
            # Find consecutive curtailment events
            df['Curtailed'] = df['Curtailment'] > 0
            df['Event'] = (df['Curtailed'] != df['Curtailed'].shift()).cumsum()
            event_durations = df[df['Curtailed']].groupby('Event').size()
            avg_duration = event_durations.mean()
        else:
            avg_duration = 0
            
        # Percentage of new load retained during curtailment hours
        if num_curtailed_hours > 0:
            avg_curtailment_depth = curtailed_hours['Curtailment'].mean() / load_addition
            avg_retention = 1 - avg_curtailment_depth
        else:
            avg_retention = 1.0
            
        return {
            'load_addition_mw': load_addition,
            'total_curtailment_mwh': total_curtailment_mwh,
            'curtailment_rate': curtailment_rate,
            'num_curtailed_hours': num_curtailed_hours,
            'avg_duration_hours': avg_duration,
            'avg_load_retention': avg_retention
        }
        
    def calculate_curtailment_with_load_addition(self, ba: str, load_addition: float) -> Optional[float]:
        """
        Calculate curtailment rate after adding new constant load.
        
        Args:
            ba: Balancing authority name
            load_addition: Constant load to add (MW)
            
        Returns:
            Curtailment rate (fraction between 0 and 1)
        """
        # Get data for this BA
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty:
            logging.warning(f"No data found for BA: {ba}")
            return None
            
        # Calculate seasonal peaks if not already done
        if ba not in self.seasonal_peaks:
            summer_peak = self.calculate_seasonal_peak(ba, 'summer')
            winter_peak = self.calculate_seasonal_peak(ba, 'winter')
            if summer_peak is None or winter_peak is None:
                return None
            self.seasonal_peaks[ba] = {'summer': summer_peak, 'winter': winter_peak}
            
        # Add month column for seasonal threshold determination
        ba_data['Month'] = ba_data['Timestamp'].dt.month
        
        # Determine seasonal threshold for each hour
        ba_data['Seasonal_Threshold'] = ba_data['Month'].apply(
            lambda m: self.seasonal_peaks[ba]['summer'] if 4 <= m <= 10 
            else self.seasonal_peaks[ba]['winter']
        )
        
        # Calculate new demand with load addition
        ba_data['New_Demand'] = ba_data['Unified Demand'] + load_addition
        
        # Calculate required curtailment
        ba_data['Excess'] = ba_data['New_Demand'] - ba_data['Seasonal_Threshold']
        ba_data['Curtailment'] = ba_data['Excess'].clip(lower=0)
        
        # Calculate curtailment rate
        total_added_energy = load_addition * len(ba_data)
        total_curtailed_energy = ba_data['Curtailment'].sum()
        
        if total_added_energy == 0:
            return 0.0
            
        return total_curtailed_energy / total_added_energy
    
    def find_load_for_curtailment_limit(self, ba: str, target_curtailment_rate: float,
                                       tolerance: float = 1e-6) -> Optional[float]:
        """
        Use goal-seek to find load addition that results in target curtailment rate.
        
        Args:
            ba: Balancing authority code
            target_curtailment_rate: Target curtailment rate (e.g., 0.0025 for 0.25%)
            tolerance: Convergence tolerance
            
        Returns:
            Load addition in MW that achieves target curtailment rate
        """
        
        # Ensure we have seasonal peaks for this BA
        if ba not in self.seasonal_peaks:
            summer_peak = self.calculate_seasonal_peak(ba, 'summer')
            winter_peak = self.calculate_seasonal_peak(ba, 'winter')
            if summer_peak is None or winter_peak is None:
                logging.warning(f"Cannot calculate seasonal peaks for BA: {ba}")
                return None
            self.seasonal_peaks[ba] = {'summer': summer_peak, 'winter': winter_peak}
        
        def objective(load_addition):
            """Objective function: difference between actual and target curtailment rate."""
            curtailment_rate = self.calculate_curtailment_with_load_addition(ba, load_addition)
            if curtailment_rate is None:
                return float('inf')
            return curtailment_rate - target_curtailment_rate
            
        # Initial bounds - start with 0 to 20% of peak demand
        peak_demand = max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
        lower_bound = 0
        upper_bound = peak_demand * 0.2
        
        # Expand upper bound if needed
        while objective(upper_bound) < 0 and upper_bound < peak_demand:
            upper_bound *= 1.5
            
        try:
            # Use root-finding to solve for exact load addition
            result = root_scalar(objective, bracket=[lower_bound, upper_bound], 
                               method='brentq', xtol=tolerance)
            return result.root
        except Exception as e:
            logging.error(f"Goal-seek failed for {ba}: {e}")
            return None
            
    def analyze_all_bas(self, curtailment_limits: List[float] = [0.0025, 0.005, 0.01, 0.05]) -> pd.DataFrame:
        """
        Analyze curtailment-enabled headroom for all loaded BAs.
        
        Args:
            curtailment_limits: List of curtailment rate limits to analyze
            
        Returns:
            DataFrame with results for each BA and curtailment limit
        """
        results = []
        
        for ba in self.ba_data.keys():
            logging.info(f"Analyzing {ba}...")
            
            for limit in curtailment_limits:
                load_mw = self.find_load_for_curtailment_limit(ba, limit)
                
                if load_mw is not None:
                    # Get detailed metrics for this load addition
                    metrics = self.calculate_curtailment(ba, load_mw)
                    
                    results.append({
                        'BA': ba,
                        'Curtailment_Limit_%': limit * 100,
                        'Max_Load_Addition_MW': load_mw,
                        'Max_Load_Addition_GW': load_mw / 1000,
                        'Curtailed_Hours_Per_Year': metrics['num_curtailed_hours'],
                        'Avg_Curtailment_Duration_Hours': metrics['avg_duration_hours'],
                        'Avg_Load_Retention_During_Curtailment_%': metrics['avg_load_retention'] * 100
                    })
                    
        return pd.DataFrame(results)
        
    def create_curtailment_curves(self, ba: str, max_load_pct: float = 0.2, 
                                 step_pct: float = 0.0025) -> pd.DataFrame:
        """
        Create curtailment curves showing relationship between load addition and curtailment.
        
        Args:
            ba: Balancing authority code
            max_load_pct: Maximum load addition as percentage of peak
            step_pct: Step size as percentage of peak
            
        Returns:
            DataFrame with load additions and corresponding curtailment rates
        """
        peak_demand = max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
        
        results = []
        load_addition = 0
        
        while load_addition <= peak_demand * max_load_pct:
            metrics = self.calculate_curtailment(ba, load_addition)
            
            results.append({
                'Load_Addition_MW': load_addition,
                'Load_Addition_GW': load_addition / 1000,
                'Load_Addition_Pct_of_Peak': (load_addition / peak_demand) * 100,
                'Curtailment_Rate_%': metrics['curtailment_rate'] * 100,
                'Curtailed_Hours': metrics['num_curtailed_hours']
            })
            
            load_addition += peak_demand * step_pct
            
        return pd.DataFrame(results)


def main():
    """Example usage of the curtailment analyzer."""
    
    # Initialize analyzer
    analyzer = CurtailmentAnalyzer()
    
    # Load data for specific BAs (or None for all)
    bas_to_analyze = ['PJM', 'MISO', 'ERCOT', 'SPP', 'SOCO']  # Top 5 from paper
    analyzer.load_ba_data(bas_to_analyze)
    
    # Calculate seasonal peaks
    analyzer.calculate_seasonal_peaks()
    
    # Analyze curtailment-enabled headroom
    results = analyzer.analyze_all_bas()
    
    # Display results
    print("\nCurtailment-Enabled Headroom Analysis")
    print("=====================================")
    print(results.to_string(index=False))
    
    # Save results
    output_dir = Path("data/analysis")
    output_dir.mkdir(exist_ok=True)
    results.to_csv(output_dir / "curtailment_headroom_analysis.csv", index=False)
    
    # Create curtailment curves for PJM as example
    if 'PJM' in analyzer.ba_data:
        curves = analyzer.create_curtailment_curves('PJM')
        curves.to_csv(output_dir / "pjm_curtailment_curves.csv", index=False)
        print(f"\nSaved curtailment curves for PJM to {output_dir}/pjm_curtailment_curves.csv")


if __name__ == "__main__":
    main()