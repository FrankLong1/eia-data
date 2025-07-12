#!/usr/bin/env python3
"""
Test to confirm that multi-year CAISO data is causing the optimization failure.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.analyze import CurtailmentAnalyzer, STANDARD_CURTAILMENT_RATES
from src.config import CLEANED_DATA_DIR, BA_LABEL_MAPPING
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_different_caiso_datasets():
    """Test optimization with different CAISO datasets."""
    
    print("="*60)
    print("TESTING DIFFERENT CAISO DATASETS")
    print("="*60)
    
    # Test datasets
    test_files = [
        ("2023 only", "cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv"),
        ("2020-2024", "cleaned_CISO_2020-01-01_2024-12-31_hourly_demand.csv"),
        ("2-day snippet", "cleaned_CISO_2023-01-01_2023-01-02_hourly_demand.csv")
    ]
    
    for dataset_name, filename in test_files:
        print(f"\n" + "="*40)
        print(f"TESTING: {dataset_name}")
        print(f"FILE: {filename}")
        print(f"="*40)
        
        file_path = Path(CLEANED_DATA_DIR) / filename
        if not file_path.exists():
            print(f"❌ File not found: {filename}")
            continue
        
        # Load data
        df = pd.read_csv(file_path)
        df['Balancing Authority'] = 'CAISO'  # Normalize BA name
        
        print(f"Dataset info:")
        print(f"  Records: {len(df):,}")
        print(f"  Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        print(f"  Demand range: {df['Demand'].min():.1f} - {df['Demand'].max():.1f} MW")
        print(f"  Mean demand: {df['Demand'].mean():.1f} MW")
        
        # Analyze seasonal characteristics
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['Month'] = df['Timestamp'].dt.month
        
        summer_data = df[df['Month'].isin([6, 7, 8])]
        winter_data = df[df['Month'].isin([12, 1, 2])]
        
        summer_peak = summer_data['Demand'].max() if len(summer_data) > 0 else 0
        winter_peak = winter_data['Demand'].max() if len(winter_data) > 0 else 0
        
        print(f"  Summer peak: {summer_peak:.1f} MW")
        print(f"  Winter peak: {winter_peak:.1f} MW")
        print(f"  Peak ratio: {summer_peak/winter_peak:.2f}" if winter_peak > 0 else "  Peak ratio: N/A")
        
        # Test optimization
        try:
            analyzer = CurtailmentAnalyzer(df)
            
            print(f"\nOptimization results:")
            success_count = 0
            for rate in STANDARD_CURTAILMENT_RATES:
                try:
                    optimal_load = analyzer.find_headroom_for_curtailment_limit('CAISO', rate)
                    if optimal_load is not None and optimal_load > 0:
                        actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', optimal_load)
                        print(f"  {rate*100:.2f}% → {optimal_load:.1f} MW (actual: {actual_rate*100:.4f}%) ✓")
                        success_count += 1
                    else:
                        print(f"  {rate*100:.2f}% → FAILED ❌")
                except Exception as e:
                    print(f"  {rate*100:.2f}% → ERROR: {e} ❌")
            
            print(f"\nSuccess rate: {success_count}/{len(STANDARD_CURTAILMENT_RATES)}")
            
        except Exception as e:
            print(f"❌ Analyzer initialization failed: {e}")

def test_combined_vs_isolated():
    """Compare combined dataset vs isolated 2023 dataset for CAISO."""
    
    print(f"\n" + "="*60)
    print(f"COMPARING COMBINED VS ISOLATED CAISO DATA")
    print(f"="*60)
    
    # Load isolated 2023 data
    isolated_file = Path(CLEANED_DATA_DIR) / "cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv"
    isolated_df = pd.read_csv(isolated_file)
    isolated_df['Balancing Authority'] = 'CAISO'
    
    # Load all CAISO data files and combine (as real pipeline does)
    caiso_files = [
        "cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv",
        "cleaned_CISO_2020-01-01_2024-12-31_hourly_demand.csv", 
        "cleaned_CISO_2023-01-01_2023-01-02_hourly_demand.csv"
    ]
    
    combined_dfs = []
    for filename in caiso_files:
        file_path = Path(CLEANED_DATA_DIR) / filename
        if file_path.exists():
            df = pd.read_csv(file_path)
            df['Balancing Authority'] = 'CAISO'
            combined_dfs.append(df)
            print(f"Loaded {filename}: {len(df):,} records")
    
    combined_df = pd.concat(combined_dfs, ignore_index=True)
    
    # Compare characteristics
    datasets = [
        ("Isolated 2023", isolated_df),
        ("Combined all", combined_df)
    ]
    
    for name, df in datasets:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['Month'] = df['Timestamp'].dt.month
        
        summer_data = df[df['Month'].isin([6, 7, 8])]
        winter_data = df[df['Month'].isin([12, 1, 2])]
        
        summer_peak = summer_data['Demand'].max() if len(summer_data) > 0 else 0
        winter_peak = winter_data['Demand'].max() if len(winter_data) > 0 else 0
        
        print(f"\n{name} dataset:")
        print(f"  Records: {len(df):,}")
        print(f"  Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        print(f"  Demand range: {df['Demand'].min():.1f} - {df['Demand'].max():.1f} MW")
        print(f"  Summer peak: {summer_peak:.1f} MW")
        print(f"  Winter peak: {winter_peak:.1f} MW")
        
        # Test 0.25% optimization specifically
        try:
            analyzer = CurtailmentAnalyzer(df)
            optimal_load = analyzer.find_headroom_for_curtailment_limit('CAISO', 0.0025)
            if optimal_load is not None and optimal_load > 0:
                print(f"  0.25% optimization: {optimal_load:.1f} MW ✓")
            else:
                print(f"  0.25% optimization: FAILED ❌")
        except Exception as e:
            print(f"  0.25% optimization: ERROR - {e} ❌")

if __name__ == "__main__":
    test_different_caiso_datasets()
    test_combined_vs_isolated()