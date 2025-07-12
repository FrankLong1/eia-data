#!/usr/bin/env python3
"""
Debug script to investigate CAISO curtailment optimization failure.
"""

import pandas as pd
import numpy as np
from src.analyze import CurtailmentAnalyzer
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_caiso_curtailment():
    """Test CAISO curtailment analysis to understand optimization failure."""
    
    # Load CAISO data
    print("Loading CAISO data...")
    df = pd.read_csv('data/cleaned/cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv')
    
    # Rename column to match expected format
    df['Balancing Authority'] = 'CAISO'
    
    print(f"CAISO data loaded: {len(df):,} records")
    print(f"Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
    print(f"Demand range: {df['Demand'].min():.1f} - {df['Demand'].max():.1f} MW")
    
    # Initialize analyzer
    analyzer = CurtailmentAnalyzer(df)
    
    # Get CAISO summary
    summary = analyzer.get_ba_summary('CAISO')
    print(f"\nCAISO Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Test different curtailment rates to see what CAISO can achieve
    print(f"\nTesting various curtailment rates for CAISO:")
    
    test_rates = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.05, 0.1]  # 0.1% to 10%
    peak_demand = max(analyzer.seasonal_peaks['CAISO']['summer'], 
                     analyzer.seasonal_peaks['CAISO']['winter'])
    
    for rate in test_rates:
        print(f"\nTesting {rate*100:.2f}% curtailment rate:")
        
        # Try a range of load additions to see what curtailment rates they produce
        test_loads = np.linspace(0, peak_demand * 0.3, 10)
        
        for load in test_loads:
            actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', load)
            if actual_rate is not None:
                print(f"  Load +{load:6.0f} MW → {actual_rate*100:.4f}% curtailment")
                
                # If we found a rate close to our target, break
                if abs(actual_rate - rate) < 0.0001:
                    print(f"    ✓ Found match for {rate*100:.2f}% target!")
                    break
        
        # Now try the optimization
        try:
            optimal_load = analyzer.find_headroom_for_curtailment_limit('CAISO', rate)
            if optimal_load is not None:
                actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', optimal_load)
                print(f"  Optimization result: {optimal_load:.1f} MW → {actual_rate*100:.4f}% curtailment")
            else:
                print(f"  Optimization failed for {rate*100:.2f}% rate")
        except Exception as e:
            print(f"  Optimization error: {e}")
    
    # Specifically test 0.25% rate with detailed debugging
    print(f"\n" + "="*60)
    print(f"DETAILED DEBUG: 0.25% curtailment rate")
    print(f"="*60)
    
    target_rate = 0.0025  # 0.25%
    
    # Test a wide range of loads manually
    print(f"\nManual curtailment curve for CAISO:")
    test_loads = np.linspace(0, peak_demand * 0.5, 20)
    
    min_rate = float('inf')
    max_rate = 0
    
    for load in test_loads:
        rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', load)
        if rate is not None:
            min_rate = min(min_rate, rate)
            max_rate = max(max_rate, rate)
            print(f"Load +{load:7.0f} MW → {rate*100:.6f}% curtailment")
    
    print(f"\nCurtailment rate range: {min_rate*100:.6f}% to {max_rate*100:.6f}%")
    print(f"Target rate {target_rate*100:.3f}% achievable: {min_rate <= target_rate <= max_rate}")
    
    # Test the optimization bounds manually
    print(f"\nTesting optimization bounds:")
    
    def curtailment_error(load_addition_mw):
        actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', load_addition_mw)
        if actual_rate is None:
            return float('inf')
        return actual_rate - target_rate
    
    # Test bounds
    min_load = 0
    max_load = peak_demand * 0.5
    
    error_at_min = curtailment_error(min_load)
    error_at_max = curtailment_error(max_load)
    
    print(f"Error at min_load ({min_load:.0f} MW): {error_at_min:.6f}")
    print(f"Error at max_load ({max_load:.0f} MW): {error_at_max:.6f}")
    
    # Check if we can bracket the solution
    if error_at_min * error_at_max > 0:
        print(f"❌ Cannot bracket solution! Both bounds have same sign.")
        print(f"   This means 0.25% is either too low or too high for CAISO.")
        if error_at_min > 0:
            print(f"   Both errors positive → even zero load gives > 0.25% curtailment")
        else:
            print(f"   Both errors negative → even max load gives < 0.25% curtailment")
    else:
        print(f"✓ Can bracket solution - optimization should work")
        
        # Try manual optimization
        try:
            from scipy.optimize import root_scalar
            result = root_scalar(curtailment_error, bracket=(min_load, max_load), method='brentq')
            print(f"Manual optimization result: {result.root:.1f} MW")
            actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', result.root)
            print(f"Verification: {actual_rate*100:.6f}% curtailment")
        except Exception as e:
            print(f"Manual optimization failed: {e}")

if __name__ == "__main__":
    test_caiso_curtailment()