#!/usr/bin/env python3
"""
Test script to run curtailment analysis with synthetic data
and compare results to the paper findings.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from analyze import CurtailmentAnalyzer

def create_synthetic_ba_data():
    """Create synthetic demand data for major balancing authorities."""
    
    # Paper's findings for comparison:
    # - 76 GW at 0.25% curtailment
    # - 98 GW at 0.5% curtailment  
    # - 126 GW at 1.0% curtailment
    # - 215 GW at 5.0% curtailment
    
    # Major BAs with approximate sizing based on the paper
    ba_configs = {
        'PJM': {'base_demand': 80000, 'peak_demand': 140000, 'winter_summer_ratio': 0.85},
        'MISO': {'base_demand': 60000, 'peak_demand': 120000, 'winter_summer_ratio': 0.80},
        'ERCOT': {'base_demand': 40000, 'peak_demand': 80000, 'winter_summer_ratio': 0.70},
        'SPP': {'base_demand': 30000, 'peak_demand': 60000, 'winter_summer_ratio': 0.75},
        'CAISO': {'base_demand': 25000, 'peak_demand': 50000, 'winter_summer_ratio': 0.65},
        'NYISO': {'base_demand': 15000, 'peak_demand': 32000, 'winter_summer_ratio': 0.85},
        'ISO-NE': {'base_demand': 12000, 'peak_demand': 28000, 'winter_summer_ratio': 0.90},
        'SOCO': {'base_demand': 20000, 'peak_demand': 45000, 'winter_summer_ratio': 0.65},
        'TVA': {'base_demand': 15000, 'peak_demand': 30000, 'winter_summer_ratio': 0.70},
        'BPA': {'base_demand': 8000, 'peak_demand': 16000, 'winter_summer_ratio': 1.1},
    }
    
    # Generate 2 years of hourly data
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2023, 12, 31, 23, 0)
    timestamps = pd.date_range(start_date, end_date, freq='H')
    
    all_data = []
    
    for ba, config in ba_configs.items():
        print(f"Generating data for {ba}...")
        
        base_demand = config['base_demand']
        peak_demand = config['peak_demand']
        winter_summer_ratio = config['winter_summer_ratio']
        
        # Create seasonal demand pattern
        demands = []
        for ts in timestamps:
            month = ts.month
            hour = ts.hour
            day_of_year = ts.timetuple().tm_yday
            
            # Seasonal variation (summer peak vs winter peak)
            if month in [6, 7, 8]:  # Summer
                seasonal_factor = 1.0
            elif month in [12, 1, 2]:  # Winter
                seasonal_factor = winter_summer_ratio
            else:  # Shoulder months
                if month in [4, 5, 9, 10]:  # Use summer pattern
                    seasonal_factor = 0.9
                else:  # Use winter pattern
                    seasonal_factor = winter_summer_ratio * 0.9
            
            # Daily cycle (peak in afternoon for summer, morning/evening for winter)
            if month in [6, 7, 8]:  # Summer peak around 3-6 PM
                daily_factor = 0.7 + 0.3 * np.sin((hour - 15) * np.pi / 12)
                if 14 <= hour <= 18:
                    daily_factor += 0.2  # Extra boost for summer peak hours
            else:  # Winter peaks morning and evening
                daily_factor = 0.7 + 0.2 * np.sin((hour - 8) * np.pi / 12) + 0.1 * np.sin((hour - 18) * np.pi / 8)
            
            # Weekly cycle (lower on weekends)
            weekly_factor = 0.9 if ts.weekday() >= 5 else 1.0
            
            # Random variation
            random_factor = np.random.normal(1.0, 0.05)
            
            # Combine all factors
            demand = base_demand * seasonal_factor * daily_factor * weekly_factor * random_factor
            
            # Ensure we hit peak demand occasionally
            if np.random.random() < 0.001:  # Rare peak events
                demand = peak_demand * np.random.uniform(0.95, 1.0)
            
            # Ensure minimum demand
            demand = max(demand, base_demand * 0.4)
            
            demands.append(demand)
        
        # Create DataFrame for this BA
        ba_data = pd.DataFrame({
            'Timestamp': timestamps,
            'Balancing Authority': ba,
            'Unified Demand': demands
        })
        
        all_data.append(ba_data)
    
    # Combine all BA data
    combined_data = pd.concat(all_data, ignore_index=True)
    
    print(f"Generated {len(combined_data):,} data points for {len(ba_configs)} BAs")
    return combined_data

def run_analysis_and_compare():
    """Run the curtailment analysis and compare to paper results."""
    
    print("="*60)
    print("CURTAILMENT ANALYSIS TEST")
    print("="*60)
    
    # Create synthetic data
    print("\n1. Creating synthetic demand data...")
    data = create_synthetic_ba_data()
    
    # Initialize analyzer
    print("\n2. Initializing curtailment analyzer...")
    analyzer = CurtailmentAnalyzer(data)
    
    # Get available BAs
    available_bas = analyzer.get_available_bas()
    print(f"Available BAs: {', '.join(available_bas)}")
    
    # Run headroom analysis
    print("\n3. Running curtailment headroom analysis...")
    results = analyzer.analyze_curtailment_headroom()
    
    if results.empty:
        print("ERROR: No results generated!")
        return
    
    # Aggregate results by curtailment rate
    print("\n4. Aggregating results...")
    
    # Group by curtailment rate and sum GW
    summary_by_rate = results.groupby('curtailment_rate').agg({
        'load_addition_gw': 'sum',
        'ba': 'count'
    }).round(1)
    
    summary_by_rate.columns = ['Total_GW', 'Num_BAs']
    
    print("\n" + "="*60)
    print("RESULTS COMPARISON")
    print("="*60)
    
    # Paper results for comparison
    paper_results = {
        0.0025: 76,   # 0.25%
        0.005: 98,    # 0.5%
        0.01: 126,    # 1.0%
        0.05: 215     # 5.0%
    }
    
    print(f"{'Curtailment Rate':<15} {'Our Result':<12} {'Paper Result':<13} {'Difference':<12} {'% Diff':<10}")
    print("-" * 70)
    
    for rate in [0.0025, 0.005, 0.01, 0.05]:
        rate_pct = rate * 100
        
        if rate in summary_by_rate.index:
            our_result = summary_by_rate.loc[rate, 'Total_GW']
            paper_result = paper_results[rate]
            difference = our_result - paper_result
            pct_diff = (difference / paper_result) * 100
            
            print(f"{rate_pct:>6.2f}%        {our_result:>8.1f} GW   {paper_result:>8} GW     {difference:>+8.1f}     {pct_diff:>+6.1f}%")
        else:
            print(f"{rate_pct:>6.2f}%        {'N/A':>8}      {paper_results[rate]:>8} GW     {'N/A':>8}     {'N/A':>6}")
    
    # Show top 5 BAs by curtailment rate
    print("\n" + "="*60)
    print("TOP 5 BAs BY HEADROOM (0.5% curtailment)")
    print("="*60)
    
    rate_05_results = results[results['curtailment_rate'] == 0.005].copy()
    if not rate_05_results.empty:
        rate_05_results = rate_05_results.sort_values('load_addition_gw', ascending=False).head(5)
        
        print("Paper's Top 5:")
        paper_top5 = [
            ("PJM", 18),
            ("MISO", 15), 
            ("ERCOT", 10),
            ("SPP", 10),
            ("SOCO", 8)
        ]
        
        for i, (ba, gw) in enumerate(paper_top5, 1):
            print(f"{i}. {ba}: {gw} GW")
        
        print("\nOur Results Top 5:")
        for i, row in enumerate(rate_05_results.itertuples(), 1):
            print(f"{i}. {row.ba}: {row.load_addition_gw:.1f} GW")
    
    # Detailed results table
    print("\n" + "="*60)
    print("DETAILED RESULTS BY BA AND CURTAILMENT RATE")
    print("="*60)
    
    # Pivot table for better viewing
    pivot_results = results.pivot(index='ba', columns='curtailment_rate', values='load_addition_gw')
    pivot_results.columns = [f"{c*100:.2f}%" for c in pivot_results.columns]
    
    print(pivot_results.round(1).to_string())
    
    # Save detailed results
    results_file = 'test_analysis_results.csv'
    results.to_csv(results_file, index=False)
    print(f"\nDetailed results saved to: {results_file}")
    
    return results

if __name__ == "__main__":
    results = run_analysis_and_compare()