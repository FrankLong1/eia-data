#!/usr/bin/env python3
"""
Optimized curtailment analysis module for EIA data project.

This module implements curtailment-enabled headroom analysis based on methodology from 
"Rethinking Load Growth" paper by Norris et al. (2025). It calculates the maximum 
constant load that can be added to each balancing authority while staying within 
specified curtailment limits.

Key functionality:
- Curtailment-enabled headroom calculation for standard rates (0.25%, 0.5%, 1.0%, 5.0%)
- Seasonal peak threshold analysis (summer vs winter)
- Load factor calculations
- Curtailment duration and pattern analysis
- Vectorized operations for improved performance
- Progress tracking for better user experience

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
    
    This class provides methods to calculate the maximum constant load that can
    be added to each balancing authority while staying within specified curtailment
    limits, following the methodology from Norris et al. (2025).
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the analyzer with cleaned BA data.
        
        Args:
            data: DataFrame with columns:
                  - Timestamp: datetime
                  - Balancing Authority: BA name
                  - Demand: demand in MW
        """
        self.data = data.copy()
        self.seasonal_peaks = {}
        self.load_factors = {}
        self.ba_data_cache = {}  # Cache BA-specific data for performance
        
        # Ensure proper datetime format
        if 'Timestamp' in self.data.columns:
            self.data['Timestamp'] = pd.to_datetime(self.data['Timestamp'])
        
        # Validate required columns
        required_columns = ['Timestamp', 'Balancing Authority', 'Demand']
        missing_cols = [col for col in required_columns if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Pre-calculate everything we can for vectorized operations
        self._precompute_all_metrics()
        
        logging.info(f"Initialized analyzer with {len(self.data):,} data points for {len(self.seasonal_peaks)} BAs")
    
    def _precompute_all_metrics(self):
        """
        Pre-compute seasonal thresholds and cache data for fast vectorized operations.
        
        This method is called during initialization and performs expensive calculations
        once rather than repeatedly during analysis. Key optimizations:
        
        1. Add month column to all data
        2. Calculate absolute maximum seasonal peaks for each BA (following paper methodology)
        3. Pre-compute seasonal thresholds for every hour
        4. Cache BA-specific data and sorted arrays
        5. Calculate load factors
        
        Performance impact: ~10x speedup during analysis phase
        """
        # Add month column for seasonal logic
        self.data['Month'] = self.data['Timestamp'].dt.month
        
        # Calculate seasonal peaks and thresholds for each BA
        for ba in self.data['Balancing Authority'].unique():
            ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
            
            # Calculate absolute maximum seasonal peaks (following paper methodology)
            # Summer months: June-August  
            summer_data = ba_data[ba_data['Month'].isin(SUMMER_MONTHS)]
            # Winter months: December-February
            winter_data = ba_data[ba_data['Month'].isin(WINTER_MONTHS)]
            
            # Use absolute maximum as per research paper (not 95th percentile)
            summer_peak = summer_data['Demand'].max() if len(summer_data) > 0 else 0
            winter_peak = winter_data['Demand'].max() if len(winter_data) > 0 else 0
            
            self.seasonal_peaks[ba] = {
                'summer': summer_peak,
                'winter': winter_peak
            }
            
            # Pre-compute seasonal thresholds for every hour based on month
            # Direct threshold assignment - clearer than confusing season labels
            ba_mask = self.data['Balancing Authority'] == ba
            
            # Summer months (Jun-Aug) and summer shoulders (Apr-May, Sep-Oct) use summer peak
            summer_months_mask = ba_mask & self.data['Month'].isin(SUMMER_MONTHS + SHOULDER_MONTHS['summer'])
            self.data.loc[summer_months_mask, 'Seasonal_Threshold'] = summer_peak
            
            # Winter months (Dec-Feb) and winter shoulders (Nov, Mar) use winter peak  
            winter_months_mask = ba_mask & self.data['Month'].isin(WINTER_MONTHS + SHOULDER_MONTHS['winter'])
            self.data.loc[winter_months_mask, 'Seasonal_Threshold'] = winter_peak
            
            # Calculate load factor
            mean_demand = ba_data['Demand'].mean()
            peak_demand = ba_data['Demand'].max()
            self.load_factors[ba] = mean_demand / peak_demand if peak_demand > 0 else 0
            
            # Cache sorted demand for fast load duration curve calculations  
            # Load duration curve = demand values ranked from highest to lowest
            # Used for: percentile queries, visualization, fast "time above X" calculations
            self.ba_data_cache[ba] = {
                'sorted_demand': np.sort(ba_data['Demand'].values)[::-1],  # Descending order
                'num_hours': len(ba_data),
                'data': ba_data
            }
    
    def get_available_bas(self) -> List[str]:
        """Get list of available BAs in the dataset."""
        return list(self.seasonal_peaks.keys())
    
    def calculate_curtailment_rate_vectorized(self, ba: str, load_addition: float) -> Optional[float]:
        """
        Fast vectorized calculation of curtailment rate for a given load addition.
        
        This is the core calculation that determines how much of the added load
        would need to be curtailed to stay within seasonal peak thresholds.
        
        Algorithm:
        1. Add constant load to all hourly demand values (vectorized)
        2. Compare augmented demand to pre-computed seasonal thresholds (vectorized)
        3. Calculate required curtailment = max(0, augmented_demand - threshold)
        4. Curtailment rate = total_curtailed_energy / total_added_energy
        
        Args:
            ba: Balancing authority name (e.g., 'PJM')
            load_addition: Constant load to add in MW (e.g., 1000.0)
            
        Returns:
            Curtailment rate as fraction 0-1 (e.g., 0.005 = 0.5%)
            None if BA data not available
        """
        if ba not in self.ba_data_cache:
            return None
        
        ba_data = self.data[self.data['Balancing Authority'] == ba]
        
        # Vectorized curtailment calculation
        augmented_demand = ba_data['Demand'].values + load_addition
        seasonal_threshold = ba_data['Seasonal_Threshold'].values
        
        curtailment = np.maximum(0, augmented_demand - seasonal_threshold)
        
        # Calculate curtailment rate
        total_added_energy = load_addition * len(ba_data)
        total_curtailed_energy = curtailment.sum()
        
        return total_curtailed_energy / total_added_energy if total_added_energy > 0 else 0
    
    def calculate_detailed_curtailment_metrics(self, ba: str, load_addition: float) -> Dict:
        """
        Calculate comprehensive curtailment statistics for a specific load addition.
        
        This method provides detailed analysis of curtailment patterns including:
        - Basic metrics: total curtailment, hours affected, curtailment rate
        - Duration analysis: average/max consecutive curtailment periods
        - Load retention: how much of added load is actually delivered
        - Seasonal breakdown: summer vs winter curtailment patterns
        
        Used after optimization finds the optimal load addition to characterize
        the curtailment that would occur at that load level.
        
        Args:
            ba: Balancing authority name
            load_addition: Load addition in MW (typically from optimization)
            
        Returns:
            Dictionary with visualization-compatible keys (uppercase):
            - BA: Balancing authority name
            - Max_Load_Addition_MW/GW: Load addition amounts
            - Curtailment_Rate/Pct: Actual curtailment achieved
            - Curtailed_Hours_Per_Year: Number of hours with curtailment
            - Avg/Max_Duration_Hours: Curtailment event duration stats
            - Seasonal_Curtailment: Summer/winter breakdown
            - Load/Peak data: Load factors and seasonal peaks
        """
        ba_data = self.data[self.data['Balancing Authority'] == ba].copy()
        
        if ba_data.empty or ba not in self.seasonal_peaks:
            return {}
        
        # Vectorized calculations
        augmented_demand = ba_data['Demand'].values + load_addition
        seasonal_threshold = ba_data['Seasonal_Threshold'].values
        curtailment = np.maximum(0, augmented_demand - seasonal_threshold)
        is_curtailed = curtailment > 0
        
        # Basic metrics
        total_curtailment_mwh = curtailment.sum()
        max_potential_mwh = load_addition * len(ba_data)
        curtailment_rate = total_curtailment_mwh / max_potential_mwh if max_potential_mwh > 0 else 0
        
        # Curtailment hours and duration
        num_curtailed_hours = is_curtailed.sum()
        
        if num_curtailed_hours > 0:
            # Find consecutive curtailment events
            diff = np.diff(np.concatenate(([0], is_curtailed.astype(int), [0])))
            starts = np.where(diff == 1)[0]
            ends = np.where(diff == -1)[0]
            durations = ends - starts
            
            avg_duration = durations.mean() if len(durations) > 0 else 0
            max_duration = durations.max() if len(durations) > 0 else 0
            
            # Load retention
            avg_curtailment_depth = curtailment[is_curtailed].mean() / load_addition
            avg_load_retention = 1 - avg_curtailment_depth
            
            # Seasonal breakdown
            summer_curtailed = is_curtailed & ba_data['Month'].isin(SUMMER_MONTHS + SHOULDER_MONTHS['summer']).values
            winter_curtailed = is_curtailed & ba_data['Month'].isin(WINTER_MONTHS + SHOULDER_MONTHS['winter']).values
            
            seasonal_breakdown = {
                'summer': int(summer_curtailed.sum()),
                'winter': int(winter_curtailed.sum())
            }
        else:
            avg_duration = 0
            max_duration = 0
            avg_load_retention = 1.0
            seasonal_breakdown = {'summer': 0, 'winter': 0}
        
        # Return with visualization-compatible column names
        return {
            'BA': ba,  # Uppercase for visualization compatibility
            'Max_Load_Addition_MW': load_addition,
            'Max_Load_Addition_GW': load_addition / 1000,
            'Curtailment_Rate': curtailment_rate,
            'Curtailment_Rate_Pct': curtailment_rate * 100,
            'Total_Curtailment_MWh': total_curtailment_mwh,
            'Curtailed_Hours_Per_Year': num_curtailed_hours,
            'Avg_Duration_Hours': avg_duration,
            'Max_Duration_Hours': max_duration,
            'Avg_Load_Retention': avg_load_retention,
            'Avg_Load_Retention_Pct': avg_load_retention * 100,
            'Seasonal_Curtailment': seasonal_breakdown,
            'Load_Factor': self.load_factors.get(ba, 0),
            'Summer_Peak_MW': self.seasonal_peaks[ba]['summer'],
            'Winter_Peak_MW': self.seasonal_peaks[ba]['winter']
        }
    
    def find_headroom_for_curtailment_limit(self, ba: str, target_curtailment_rate: float,
                                          tolerance: float = 1e-6) -> Optional[float]:
        """
        Find maximum load addition that achieves a specific annual curtailment rate.
        
        PROBLEM: What's the largest constant load we can add while keeping 
                 annual curtailment at exactly X% (e.g., 0.5%)?
        
        SOLUTION: Try different load additions until we find one where:
                  calculate_curtailment_rate_vectorized(load) = target_rate
        
        EXAMPLE: If target = 0.5%, keep trying loads until curtailment = exactly 0.5%
                 Maybe 1000 MW → 0.3% (too low), 2000 MW → 0.7% (too high)
                 So optimal is somewhere around 1600 MW → 0.5% (perfect!)
        
        Args:
            ba: Balancing authority name  
            target_curtailment_rate: Annual curtailment target (e.g., 0.005 = 0.5%)
            tolerance: Optimization precision (1e-6 ≈ 1 kW accuracy)
            
        Returns:
            Optimal load addition in MW, or None if optimization fails
        """
        if ba not in self.seasonal_peaks:
            logging.warning(f"No seasonal peak data for BA: {ba}")
            return None
        
        # OPTIMIZATION SETUP: Find load where curtailment_rate(load) = target
        def curtailment_error(load_addition_mw):
            """
            Calculate how far we are from the target curtailment rate.
            Returns 0 when curtailment_rate(load) exactly equals target.
            
            Examples:
            - If target=0.5% and actual=0.3%, returns -0.2% (need more load)
            - If target=0.5% and actual=0.7%, returns +0.2% (too much load)
            - If target=0.5% and actual=0.5%, returns 0 (perfect!)
            """
            actual_curtailment_rate = self.calculate_curtailment_rate_vectorized(ba, load_addition_mw)
            if actual_curtailment_rate is None:
                return float('inf')  # Invalid load addition
            
            # Return difference: positive = too much curtailment, negative = too little
            return actual_curtailment_rate - target_curtailment_rate
        
        # SET SEARCH BOUNDS: Start with reasonable range
        peak_demand = max(self.seasonal_peaks[ba]['summer'], self.seasonal_peaks[ba]['winter'])
        min_load = 0  # Can't add negative load
        max_load = peak_demand * 0.5  # Start conservatively at 50% of peak
        
        # EXPAND BOUNDS if needed - make sure we can bracket the solution
        for _ in range(10):  # Safety limit
            try:
                error_at_max = curtailment_error(max_load)
                if error_at_max > 0:  # Good - this load gives too much curtailment
                    break
                max_load *= 2  # Try higher load
            except:
                max_load *= 2
        
        # NUMERICAL OPTIMIZATION: Binary search using scipy's root_scalar
        # This keeps trying different loads until curtailment_rate(load) = target_rate
        # Essentially: if curtailment too low → try more load, if too high → try less load
        try:
            result = root_scalar(
                curtailment_error,
                bracket=(min_load, max_load),
                method='brentq',  # Robust binary search method
                xtol=tolerance
            )
            return result.root
        except Exception as e:
            # This can happen when curtailment rate is not achievable (e.g., 0.25% too low)
            logging.debug(f"Binary search optimization failed for {ba}: {e}")
            return None  # Return None instead of crashing
    
    # Removed redundant calculate_headroom_for_ba() - logic moved into main analyze method
    
    def analyze_curtailment_headroom(self, ba_list: List[str] = None, 
                                   curtailment_limits: List[float] = None) -> pd.DataFrame:
        """
        MAIN ANALYSIS: Calculate curtailment headroom for multiple BAs and curtailment targets.
        
        For each balancing authority, this method tests multiple annual curtailment targets
        (e.g., 0.25%, 0.5%, 1%, 5%) to find the optimal load addition for each target.
        
        Process:
        1. For each BA (PJM, MISO, etc.)
        2. For each annual curtailment target (0.25%, 0.5%, 1%, 5%)
        3. Find maximum constant load addition that achieves exactly that curtailment rate
        4. Calculate detailed metrics (hours curtailed, seasonal patterns, etc.)
        5. Combine all results into comprehensive DataFrame
        
        Args:
            ba_list: List of BA names to analyze (None = all available BAs)
            curtailment_limits: List of ANNUAL curtailment rates (REQUIRED)
                               e.g., [0.0025, 0.005, 0.01, 0.05] = 0.25%, 0.5%, 1%, 5% per year
            
        Returns:
            DataFrame with one row per (BA, curtailment_target) combination
            Contains load additions, curtailment metrics, seasonal breakdowns, etc.
        """
        # Validate inputs
        if ba_list is None:
            ba_list = self.get_available_bas()
        if curtailment_limits is None:
            raise ValueError("curtailment_limits must be explicitly provided")
        
        all_results = []
        total_bas = len(ba_list)

        # MAIN LOOP: Process each BA
        for i, ba in enumerate(ba_list):
            logging.info(f"Analyzing curtailment headroom for {ba}... ({i+1}/{total_bas})")
            
            # Test each annual curtailment target (0.25%, 0.5%, 1%, 5%)
            # NOTE: This is NOT separate summer/winter analysis - it's one year-round analysis
            # that uses summer thresholds during summer months and winter thresholds during winter months
            for limit in curtailment_limits:
                logging.debug(f"  Binary search for {limit*100:.2f}% annual curtailment target...")
                
                # STEP 1: Binary search optimization to find maximum year-round load addition
                # Finds largest constant load that achieves exactly 'limit' annual curtailment
                # Uses pre-computed seasonal thresholds (summer peaks Jun-Oct, winter peaks Nov-May)
                max_load = self.find_headroom_for_curtailment_limit(ba, limit)
                
                # STEP 2: Calculate comprehensive metrics for this optimal load
                # Handle cases where optimization fails (e.g., curtailment rate not achievable)
                if max_load is None or max_load <= 0:
                    logging.warning(f"Skipping {ba} at {limit*100:.2f}% curtailment - rate not achievable with current data")
                    continue
                
                metrics = self.calculate_detailed_curtailment_metrics(ba, max_load)
                all_results.append(metrics)
        
        # Combine and return results
        if len(all_results) == 0:
            logging.error("No valid results produced - all optimizations failed")
            return pd.DataFrame()
        
        results_df = pd.DataFrame(all_results)
        results_df = results_df.sort_values(['BA', 'Curtailment_Rate'])
        
        logging.info(f"Analysis complete: {len(results_df)} total result rows")
        return results_df
    
    @staticmethod
    def print_results_summary(results_df: pd.DataFrame):
        """
        Print a clean, readable summary of curtailment analysis results.
        
        Args:
            results_df: DataFrame with analysis results
        """
        if results_df.empty:
            print("No results to display")
            return
        
        print("\n" + "="*80)
        print("CURTAILMENT ANALYSIS RESULTS")
        print("="*80)
        
        # Get unique curtailment rates and sort them
        curtailment_rates = sorted(results_df['Curtailment_Rate_Pct'].unique())
        
        for rate_pct in curtailment_rates:
            print(f"\n**{rate_pct:.2f}% Curtailment Rate:**")
            
            # Filter results for this curtailment rate
            rate_results = results_df[results_df['Curtailment_Rate_Pct'] == rate_pct].copy()
            rate_results = rate_results.sort_values('Max_Load_Addition_GW', ascending=False)
            
            total_gw = 0
            for _, row in rate_results.iterrows():
                ba_name = row['BA']
                load_gw = row['Max_Load_Addition_GW']
                total_gw += load_gw
                
                # Shorten some long BA names for readability
                if "Midcontinent Independent System Operator" in ba_name:
                    ba_name = "MISO"
                elif "PJM Interconnection" in ba_name:
                    ba_name = "PJM"
                elif "Electric Reliability Council of Texas" in ba_name:
                    ba_name = "ERCOT"
                elif "California Independent System Operator" in ba_name:
                    ba_name = "CAISO"
                elif "New York Independent System Operator" in ba_name:
                    ba_name = "NYISO"
                elif "Southern Company Services" in ba_name:
                    ba_name = "Southern Company"
                elif "Southwest Power Pool" in ba_name:
                    ba_name = "SPP"
                elif "Florida Power & Light" in ba_name:
                    ba_name = "Florida P&L"
                elif "Duke Energy Carolinas" == ba_name:
                    ba_name = "Duke Carolinas"
                elif "Tennessee Valley Authority" == ba_name:
                    ba_name = "TVA"
                elif "Arizona Public Service" in ba_name:
                    ba_name = "Arizona Public Service"
                elif "Bonneville Power Administration" == ba_name:
                    ba_name = "BPA"
                
                print(f"- {ba_name}: {load_gw:.1f} GW")
            
            print(f"**TOTAL: {total_gw:.1f} GW**")
        
        print("\n" + "="*80)
        print(f"Analysis covered {len(results_df['BA'].unique())} balancing authorities")
        print(f"Total result combinations: {len(results_df)}")
        
        # Show which BAs had optimization failures
        all_bas = set(results_df['BA'].unique())
        expected_results = len(all_bas) * len(curtailment_rates)
        if len(results_df) < expected_results:
            missing_count = expected_results - len(results_df)
            print(f"Note: {missing_count} optimization(s) failed (rates not achievable)")
        
        print("="*80)
    
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
            curtailment_rate = self.calculate_curtailment_rate_vectorized(ba, load_addition)
            if curtailment_rate is not None:
                results.append({
                    'BA': ba,
                    'Max_Load_Addition_MW': load_addition,
                    'Max_Load_Addition_GW': load_addition / 1000,
                    'Load_Addition_Pct_Of_Peak': (load_addition / peak_demand) * 100,
                    'Curtailment_Rate': curtailment_rate,
                    'Curtailment_Rate_Pct': curtailment_rate * 100
                })
        
        return pd.DataFrame(results)
    
    def get_ba_summary(self, ba: str) -> Dict:
        """
        Get summary statistics for a BA.
        
        Args:
            ba: Balancing authority
            
        Returns:
            Dictionary with BA statistics
        """
        if ba not in self.ba_data_cache:
            return {}
        
        ba_data = self.ba_data_cache[ba]['data']
        
        return {
            'BA': ba,
            'Data_Points': len(ba_data),
            'Start_Date': ba_data['Timestamp'].min().strftime('%Y-%m-%d'),
            'End_Date': ba_data['Timestamp'].max().strftime('%Y-%m-%d'),
            'Summer_Peak_MW': self.seasonal_peaks[ba]['summer'],
            'Winter_Peak_MW': self.seasonal_peaks[ba]['winter'],
            'Load_Factor': self.load_factors.get(ba, 0),
            'Avg_Demand_MW': ba_data['Demand'].mean(),
            'Min_Demand_MW': ba_data['Demand'].min(),
            'Max_Demand_MW': ba_data['Demand'].max()
        }
    
    def get_seasonal_patterns(self, ba: str) -> Dict:
        """
        Analyze seasonal demand patterns.
        
        Args:
            ba: Balancing authority
            
        Returns:
            Dictionary with seasonal statistics
        """
        if ba not in self.ba_data_cache:
            return {}
        
        ba_data = self.ba_data_cache[ba]['data']
        ba_data['Season'] = ba_data['Timestamp'].dt.month.apply(
            lambda m: 'summer' if m in SUMMER_MONTHS + SHOULDER_MONTHS['summer'] else 'winter'
        )
        
        seasonal_stats = ba_data.groupby('Season')['Demand'].agg([
            'mean', 'std', 'min', 'max', 'count'
        ])
        
        return {
            'BA': ba,
            'Seasonal_Stats': seasonal_stats.to_dict(),
            'Summer_Winter_Peak_Ratio': (self.seasonal_peaks[ba]['summer'] / 
                                       self.seasonal_peaks[ba]['winter'] 
                                       if self.seasonal_peaks[ba]['winter'] > 0 else 0),
            'Load_Factor': self.load_factors.get(ba, 0)
        }


# Removed redundant load_cleaned_data() and main() 
# Use run_analysis.py as the single entry point instead