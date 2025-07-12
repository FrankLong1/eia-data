#!/usr/bin/env python3
"""
Test the analysis with combined data as done in the real pipeline.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.analyze import CurtailmentAnalyzer, STANDARD_CURTAILMENT_RATES
from src.config import CLEANED_DATA_DIR, BA_LABEL_MAPPING
import logging
import traceback

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def load_combined_data(data_dir):
    """Load and combine all CSV files from a directory (same as run_analysis.py)."""
    data_path = Path(data_dir)
    
    files = list(data_path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    print(f"Found {len(files)} cleaned data files:")
    for f in files:
        print(f"  {f.name}")
    
    all_data = []
    for file_path in files:
        print(f"Loading {file_path.name}...")
        df = pd.read_csv(file_path)
        print(f"  {len(df):,} records, BA: {df['Balancing Authority'].unique()}")
        all_data.append(df)
    
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nCombined data: {len(combined):,} records")
    
    return combined

def apply_ba_mapping(df):
    """Apply BA label mapping as done in cleaning process."""
    # Apply the mapping to standardize BA names
    df['Balancing Authority'] = df['Balancing Authority'].replace(BA_LABEL_MAPPING)
    
    # Also apply common name mappings
    common_mappings = {
        'California Independent System Operator': 'CAISO',
        'Electric Reliability Council of Texas, Inc.': 'ERCOT',
        'PJM Interconnection, LLC': 'PJM',
        'Midcontinent Independent System Operator, Inc.': 'MISO'
    }
    df['Balancing Authority'] = df['Balancing Authority'].replace(common_mappings)
    
    return df

def test_combined_analysis():
    """Test analysis with all combined data."""
    
    print("="*60)
    print("TESTING COMBINED DATA ANALYSIS")
    print("="*60)
    
    # Load combined data exactly as the real pipeline does
    combined_data = load_combined_data(CLEANED_DATA_DIR)
    
    # Apply BA mappings
    combined_data = apply_ba_mapping(combined_data)
    
    # Check the BAs in combined data
    ba_counts = combined_data['Balancing Authority'].value_counts()
    print(f"\nBA distribution in combined data:")
    for ba, count in ba_counts.items():
        print(f"  {ba}: {count:,} records")
    
    # Check if CAISO is present
    if 'CAISO' not in ba_counts:
        print("❌ CAISO not found in combined data!")
        return
    
    print(f"\n✓ CAISO found with {ba_counts['CAISO']:,} records")
    
    # Initialize analyzer
    analyzer = CurtailmentAnalyzer(combined_data)
    available_bas = analyzer.get_available_bas()
    print(f"\nAvailable BAs after initialization: {len(available_bas)}")
    for ba in sorted(available_bas):
        print(f"  {ba}")
    
    # Test CAISO specifically
    if 'CAISO' in available_bas:
        print(f"\n" + "="*40)
        print(f"TESTING CAISO OPTIMIZATION")
        print(f"="*40)
        
        # Get CAISO summary
        summary = analyzer.get_ba_summary('CAISO')
        print(f"\nCAISO summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        # Test each curtailment rate
        for rate in STANDARD_CURTAILMENT_RATES:
            print(f"\nTesting {rate*100:.2f}% curtailment:")
            try:
                optimal_load = analyzer.find_headroom_for_curtailment_limit('CAISO', rate)
                if optimal_load is not None and optimal_load > 0:
                    actual_rate = analyzer.calculate_curtailment_rate_vectorized('CAISO', optimal_load)
                    print(f"  ✓ Success: {optimal_load:.1f} MW → {actual_rate*100:.4f}% curtailment")
                else:
                    print(f"  ❌ Failed: returned {optimal_load}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                traceback.print_exc()
        
        # Try full analysis
        print(f"\n" + "="*40)
        print(f"TESTING FULL ANALYSIS")
        print(f"="*40)
        
        try:
            results = analyzer.analyze_curtailment_headroom(
                ba_list=['CAISO'],
                curtailment_limits=STANDARD_CURTAILMENT_RATES
            )
            print("✓ Full analysis succeeded!")
            print(results[['BA', 'Curtailment_Rate_Pct', 'Max_Load_Addition_MW']])
            
        except Exception as e:
            print(f"❌ Full analysis failed: {e}")
            traceback.print_exc()
    
    else:
        print("❌ CAISO not found in available BAs after analyzer initialization!")

def debug_data_inconsistencies():
    """Debug potential data inconsistencies between isolated and combined loading."""
    
    print("\n" + "="*60)
    print("DEBUGGING DATA INCONSISTENCIES")
    print("="*60)
    
    # Load CAISO data in isolation
    caiso_file = Path(CLEANED_DATA_DIR) / "cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv"
    isolated_data = pd.read_csv(caiso_file)
    isolated_data = apply_ba_mapping(isolated_data)
    
    print(f"Isolated CAISO data:")
    print(f"  Records: {len(isolated_data):,}")
    print(f"  BA values: {isolated_data['Balancing Authority'].unique()}")
    print(f"  Demand range: {isolated_data['Demand'].min():.1f} - {isolated_data['Demand'].max():.1f}")
    
    # Load combined data and extract CAISO
    combined_data = load_combined_data(CLEANED_DATA_DIR)
    combined_data = apply_ba_mapping(combined_data)
    combined_caiso = combined_data[combined_data['Balancing Authority'] == 'CAISO'].copy()
    
    print(f"\nCombined CAISO data:")
    print(f"  Records: {len(combined_caiso):,}")
    print(f"  BA values: {combined_caiso['Balancing Authority'].unique()}")
    print(f"  Demand range: {combined_caiso['Demand'].min():.1f} - {combined_caiso['Demand'].max():.1f}")
    
    # Compare the data
    if len(isolated_data) != len(combined_caiso):
        print(f"❌ Record count mismatch!")
    else:
        print(f"✓ Record counts match")
    
    # Check if demand values are identical
    isolated_sorted = sorted(isolated_data['Demand'].values)
    combined_sorted = sorted(combined_caiso['Demand'].values)
    
    if np.allclose(isolated_sorted, combined_sorted):
        print(f"✓ Demand values are identical")
    else:
        print(f"❌ Demand values differ!")
        diff_count = sum(1 for a, b in zip(isolated_sorted, combined_sorted) if not np.isclose(a, b))
        print(f"  {diff_count} values differ out of {len(isolated_sorted)}")

if __name__ == "__main__":
    test_combined_analysis()
    debug_data_inconsistencies()