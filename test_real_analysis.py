#!/usr/bin/env python3
"""
Test the actual analysis that's failing to see exactly where the issue occurs.
"""

import pandas as pd
import numpy as np
from src.analyze import CurtailmentAnalyzer, STANDARD_CURTAILMENT_RATES
import logging
import traceback

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_real_analysis():
    """Test the actual analysis pipeline that's failing."""
    
    # Load CAISO data exactly as the real analysis would
    print("Loading CAISO data...")
    df = pd.read_csv('data/cleaned/cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv')
    
    # Map CISO to CAISO as done in the real analysis
    df['Balancing Authority'] = df['Balancing Authority'].replace({
        'California Independent System Operator': 'CAISO'
    })
    
    print(f"CAISO data loaded: {len(df):,} records")
    print(f"Balancing Authority values: {df['Balancing Authority'].unique()}")
    
    # Initialize analyzer
    analyzer = CurtailmentAnalyzer(df)
    
    print(f"Available BAs: {analyzer.get_available_bas()}")
    
    # Try the exact analysis that's failing
    print(f"\nTesting with standard curtailment rates: {[r*100 for r in STANDARD_CURTAILMENT_RATES]}%")
    
    try:
        # This should be the exact call that's failing
        results = analyzer.analyze_curtailment_headroom(
            ba_list=['CAISO'],
            curtailment_limits=STANDARD_CURTAILMENT_RATES
        )
        print("✓ Analysis succeeded!")
        print(results[['BA', 'Curtailment_Rate_Pct', 'Max_Load_Addition_MW']])
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        print("Full traceback:")
        traceback.print_exc()
        
        # Try to isolate which curtailment rate is failing
        print(f"\nTesting each curtailment rate individually:")
        for rate in STANDARD_CURTAILMENT_RATES:
            try:
                print(f"Testing {rate*100:.2f}% rate...")
                optimal_load = analyzer.find_headroom_for_curtailment_limit('CAISO', rate)
                if optimal_load is not None and optimal_load > 0:
                    print(f"  ✓ {rate*100:.2f}% → {optimal_load:.1f} MW")
                else:
                    print(f"  ❌ {rate*100:.2f}% → {optimal_load}")
            except Exception as rate_error:
                print(f"  ❌ {rate*100:.2f}% → Error: {rate_error}")

def test_data_format_issue():
    """Test if there's a data format issue causing the problem."""
    
    print("\n" + "="*60)
    print("TESTING DATA FORMAT ISSUES")
    print("="*60)
    
    # Load the data and check its structure
    df = pd.read_csv('data/cleaned/cleaned_CISO_2023-01-01_2023-12-31_hourly_demand.csv')
    
    print("Original data structure:")
    print(f"Columns: {list(df.columns)}")
    print(f"BA column values: {df['Balancing Authority'].unique()}")
    print(f"Sample rows:")
    print(df.head())
    
    # Check if we need to handle different BA naming
    print(f"\nBA value counts:")
    print(df['Balancing Authority'].value_counts())
    
    # Test with original BA name vs mapped name
    test_cases = [
        ('California Independent System Operator', 'Original BA name'),
        ('CAISO', 'Mapped BA name'),
        ('CISO', 'API code name')
    ]
    
    for ba_name, description in test_cases:
        print(f"\nTesting with {description}: '{ba_name}'")
        
        # Create test dataframe
        test_df = df.copy()
        test_df['Balancing Authority'] = ba_name
        
        try:
            analyzer = CurtailmentAnalyzer(test_df)
            available_bas = analyzer.get_available_bas()
            print(f"  Available BAs: {available_bas}")
            
            if ba_name in available_bas:
                # Test 0.25% rate specifically
                optimal_load = analyzer.find_headroom_for_curtailment_limit(ba_name, 0.0025)
                print(f"  0.25% curtailment → {optimal_load:.1f} MW" if optimal_load else f"  0.25% curtailment → Failed")
            else:
                print(f"  BA '{ba_name}' not found in available BAs")
                
        except Exception as e:
            print(f"  Error with '{ba_name}': {e}")

if __name__ == "__main__":
    test_real_analysis()
    test_data_format_issue()