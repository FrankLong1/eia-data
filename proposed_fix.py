#!/usr/bin/env python3
"""
Proposed fix for CAISO curtailment optimization failure.

The issue is that multiple overlapping CAISO data files are being loaded,
creating a combined dataset where the 0.25% curtailment rate is not achievable.

This script demonstrates the fix by filtering overlapping data.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.analyze import CurtailmentAnalyzer, STANDARD_CURTAILMENT_RATES
from src.config import CLEANED_DATA_DIR, BA_LABEL_MAPPING
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_combined_data_with_deduplication(data_dir):
    """
    Load and combine CSV files, avoiding overlapping time periods.
    
    Strategy: For each BA, use the most recent complete year of data
    to avoid overlapping periods that create optimization issues.
    """
    data_path = Path(data_dir)
    files = list(data_path.glob("*.csv"))
    
    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    # Group files by BA
    ba_files = {}
    for file_path in files:
        # Extract BA from filename (format: cleaned_{BA}_{start}_{end}_hourly_demand.csv)
        parts = file_path.stem.split('_')
        if len(parts) >= 2:
            ba = parts[1]
            
            # Load file to check its properties
            df = pd.read_csv(file_path)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            start_date = df['Timestamp'].min()
            end_date = df['Timestamp'].max()
            record_count = len(df)
            
            if ba not in ba_files:
                ba_files[ba] = []
            
            ba_files[ba].append({
                'file': file_path,
                'start': start_date,
                'end': end_date,
                'records': record_count,
                'df': df
            })
    
    print(f"Found files for {len(ba_files)} BAs:")
    
    # For each BA, select the best dataset
    selected_data = []
    for ba, file_list in ba_files.items():
        print(f"\n{ba}:")
        for f in file_list:
            print(f"  {f['file'].name}: {f['records']:,} records, {f['start'].date()} to {f['end'].date()}")
        
        # Selection strategy: prefer complete years, then most recent, then most records
        def score_dataset(f):
            # Score based on completeness and recency
            days = (f['end'] - f['start']).days + 1
            years = days / 365.25
            
            # Prefer complete years
            year_completeness = 1.0 if abs(years - round(years)) < 0.1 else 0.5
            
            # Prefer more recent data
            recency_score = f['end'].year / 2024.0
            
            # Prefer more data (but not as important)
            data_score = min(f['records'] / 10000, 1.0) * 0.3
            
            return year_completeness + recency_score + data_score
        
        # Select best file
        best_file = max(file_list, key=score_dataset)
        print(f"  → Selected: {best_file['file'].name}")
        
        # Apply BA mapping
        df = best_file['df'].copy()
        
        # Apply standard BA mappings
        df['Balancing Authority'] = df['Balancing Authority'].replace(BA_LABEL_MAPPING)
        
        # Apply common name mappings
        common_mappings = {
            'California Independent System Operator': 'CAISO',
            'Electric Reliability Council of Texas, Inc.': 'ERCOT',
            'PJM Interconnection, LLC': 'PJM',
            'Midcontinent Independent System Operator, Inc.': 'MISO',
            'Southwest Power Pool': 'SPP',
            'New York Independent System Operator': 'NYISO',
            'ISO New England': 'ISO-NE',
            'Duke Energy Carolinas': 'DEC',
            'Duke Energy Progress East': 'DEP', 
            'Duke Energy Florida, Inc.': 'DEF',
            'Bonneville Power Administration': 'BPA',
            'Dominion Energy South Carolina, Inc.': 'DESC',
            'South Carolina Public Service Authority': 'SCP',
            'Southern Company Services, Inc. - Trans': 'SOCO',
            'Tennessee Valley Authority': 'TVA',
            'Arizona Public Service Company': 'AZPS',
            'Florida Power & Light Co.': 'FPL',
            'PacifiCorp East': 'PACE',
            'PacifiCorp West': 'PACW',
            'Portland General Electric Company': 'PGE',
            'Public Service Company of Colorado': 'PSCO',
            'Salt River Project Agricultural Improvement and Power District': 'SRP'
        }
        df['Balancing Authority'] = df['Balancing Authority'].replace(common_mappings)
        
        selected_data.append(df)
    
    combined = pd.concat(selected_data, ignore_index=True)
    print(f"\nCombined deduplicated data: {len(combined):,} records")
    
    return combined

def test_fix():
    """Test the proposed fix."""
    
    print("="*60)
    print("TESTING PROPOSED FIX")
    print("="*60)
    
    # Load data with deduplication
    combined_data = load_combined_data_with_deduplication(CLEANED_DATA_DIR)
    
    # Check CAISO specifically
    caiso_data = combined_data[combined_data['Balancing Authority'] == 'CAISO']
    
    if len(caiso_data) == 0:
        print("❌ No CAISO data found after deduplication!")
        return
    
    print(f"\nCAISO after deduplication:")
    print(f"  Records: {len(caiso_data):,}")
    print(f"  Date range: {caiso_data['Timestamp'].min()} to {caiso_data['Timestamp'].max()}")
    print(f"  Demand range: {caiso_data['Demand'].min():.1f} - {caiso_data['Demand'].max():.1f} MW")
    
    # Test optimization
    try:
        analyzer = CurtailmentAnalyzer(combined_data)
        
        print(f"\nTesting CAISO optimization:")
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
        
        # Test full analysis
        if success_count == len(STANDARD_CURTAILMENT_RATES):
            print(f"\n✅ All optimizations succeeded! Testing full analysis...")
            results = analyzer.analyze_curtailment_headroom(
                ba_list=['CAISO'],
                curtailment_limits=STANDARD_CURTAILMENT_RATES
            )
            print("✅ Full analysis completed successfully!")
            print(results[['BA', 'Curtailment_Rate_Pct', 'Max_Load_Addition_MW']])
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")

def compare_old_vs_new():
    """Compare old approach vs new approach."""
    
    print(f"\n" + "="*60)
    print(f"COMPARING OLD VS NEW APPROACH")
    print(f"="*60)
    
    # Old approach - load all files
    print("OLD APPROACH (current broken behavior):")
    all_files = list(Path(CLEANED_DATA_DIR).glob("*CISO*.csv"))
    old_data = []
    for f in all_files:
        df = pd.read_csv(f)
        df['Balancing Authority'] = 'CAISO'
        old_data.append(df)
    
    old_combined = pd.concat(old_data, ignore_index=True)
    print(f"  Total CAISO records: {len(old_combined):,}")
    
    try:
        old_analyzer = CurtailmentAnalyzer(old_combined)
        old_result = old_analyzer.find_headroom_for_curtailment_limit('CAISO', 0.0025)
        print(f"  0.25% optimization: {'✓' if old_result else '❌'}")
    except:
        print(f"  0.25% optimization: ❌")
    
    # New approach - deduplicated
    print("\nNEW APPROACH (proposed fix):")
    new_combined = load_combined_data_with_deduplication(CLEANED_DATA_DIR)
    new_caiso = new_combined[new_combined['Balancing Authority'] == 'CAISO']
    print(f"  Total CAISO records: {len(new_caiso):,}")
    
    try:
        new_analyzer = CurtailmentAnalyzer(new_combined)
        new_result = new_analyzer.find_headroom_for_curtailment_limit('CAISO', 0.0025)
        print(f"  0.25% optimization: {'✓' if new_result else '❌'}")
    except:
        print(f"  0.25% optimization: ❌")

if __name__ == "__main__":
    test_fix()
    compare_old_vs_new()