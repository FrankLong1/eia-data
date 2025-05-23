#!/usr/bin/env python3
"""
Run curtailment analysis on cleaned EIA data.

This script demonstrates how to use the CurtailmentAnalyzer to analyze
curtailment-enabled headroom for different balancing authorities.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from BAAggregateCurtailmentAnalyzer import CurtailmentAnalyzer
import warnings
warnings.filterwarnings('ignore')

# Setup paths
project_root = Path(__file__).parent.parent.parent
cleaned_data_dir = project_root / "ba_aggregate_data" / "cleaned"
viz_dir = project_root / "ba_aggregate_data" / "visualizations"
viz_dir.mkdir(exist_ok=True)

# Load all cleaned data
print("Loading cleaned EIA data...")
all_data = []
for ba_dir in cleaned_data_dir.glob("*"):
    if ba_dir.is_dir():
        for file in ba_dir.glob("*.csv"):
            df = pd.read_csv(file)
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            all_data.append(df)

if not all_data:
    print("No processed data found. Please run data cleaning first.")
    exit(1)

# Combine all data
combined_df = pd.concat(all_data, ignore_index=True)
print(f"Loaded {len(combined_df):,} rows of data")

# Remove duplicate timestamps per BA
print("Removing duplicate timestamps...")
pre_dedup = len(combined_df)
combined_df = combined_df.drop_duplicates(subset=['Timestamp', 'Balancing Authority'], keep='first')
post_dedup = len(combined_df)
print(f"Removed {pre_dedup - post_dedup:,} duplicate records")
print(f"Final dataset: {post_dedup:,} rows")

# Initialize analyzer
analyzer = CurtailmentAnalyzer(combined_df)

# Get unique BAs
unique_bas = combined_df['Balancing Authority'].unique()
print(f"\nFound {len(unique_bas)} unique Balancing Authorities")

# Curtailment limits to analyze (from the paper)
curtailment_limits = [0.0025, 0.005, 0.01, 0.05]  # 0.25%, 0.5%, 1%, 5%

# Run analysis for top BAs by demand
print("\nAnalyzing top BAs by average demand...")
avg_demand_by_ba = combined_df.groupby('Balancing Authority')['Unified Demand'].mean().sort_values(ascending=False)
top_bas = avg_demand_by_ba.head(10).index.tolist()

results = []
for ba in top_bas:
    print(f"\nAnalyzing {ba}...")
    ba_data = combined_df[combined_df['Balancing Authority'] == ba].copy()
    
    # Calculate seasonal peaks
    summer_peak = analyzer.calculate_seasonal_peak(ba, 'summer')
    winter_peak = analyzer.calculate_seasonal_peak(ba, 'winter')
    
    if summer_peak is None or winter_peak is None:
        print(f"  Insufficient data for {ba}")
        continue
        
    print(f"  Summer peak: {summer_peak:,.0f} MW")
    print(f"  Winter peak: {winter_peak:,.0f} MW")
    
    # Find maximum load additions for each curtailment limit
    for limit in curtailment_limits:
        max_load = analyzer.find_load_for_curtailment_limit(ba, limit)
        if max_load is not None:
            # Calculate percentage of peak
            peak = max(summer_peak, winter_peak)
            pct_of_peak = (max_load / peak) * 100
            
            results.append({
                'BA': ba,
                'Curtailment_Limit': limit * 100,
                'Max_Load_MW': max_load,
                'Peak_MW': peak,
                'Load_as_Pct_Peak': pct_of_peak
            })
            
            print(f"  {limit*100:.2f}% curtailment: {max_load:,.0f} MW ({pct_of_peak:.1f}% of peak)")

# Create results DataFrame
results_df = pd.DataFrame(results)

# Save results
results_file = viz_dir / "curtailment_analysis_results.csv"
results_df.to_csv(results_file, index=False)
print(f"\nResults saved to {results_file}")

# Create visualization
print("\nCreating visualizations...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Plot 1: Maximum load by curtailment limit
for ba in results_df['BA'].unique():
    ba_data = results_df[results_df['BA'] == ba]
    ax1.plot(ba_data['Curtailment_Limit'], ba_data['Max_Load_MW'], 
             marker='o', label=ba, linewidth=2)

ax1.set_xlabel('Curtailment Limit (%)')
ax1.set_ylabel('Maximum Additional Load (MW)')
ax1.set_title('Maximum Load Addition vs Curtailment Limit')
ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
ax1.grid(True, alpha=0.3)

# Plot 2: Load as percentage of peak
for ba in results_df['BA'].unique():
    ba_data = results_df[results_df['BA'] == ba]
    ax2.plot(ba_data['Curtailment_Limit'], ba_data['Load_as_Pct_Peak'], 
             marker='o', label=ba, linewidth=2)

ax2.set_xlabel('Curtailment Limit (%)')
ax2.set_ylabel('Maximum Load as % of Peak')
ax2.set_title('Relative Load Addition Potential')
ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
viz_file = viz_dir / "curtailment_analysis_plots.png"
plt.savefig(viz_file, dpi=300, bbox_inches='tight')
print(f"Visualization saved to {viz_file}")

# Generate curtailment curves for one example BA
if len(top_bas) > 0:
    example_ba = top_bas[0]
    print(f"\nGenerating curtailment curve for {example_ba}...")
    
    # Test different load additions
    load_additions = np.linspace(0, 10000, 50)  # 0 to 10,000 MW
    curtailment_rates = []
    
    for load in load_additions:
        rate = analyzer.calculate_curtailment_with_load_addition(example_ba, load)
        if rate is not None:
            curtailment_rates.append(rate * 100)  # Convert to percentage
        else:
            curtailment_rates.append(np.nan)
    
    # Plot curtailment curve
    plt.figure(figsize=(10, 6))
    plt.plot(load_additions, curtailment_rates, linewidth=2)
    plt.xlabel('Additional Load (MW)')
    plt.ylabel('Curtailment Rate (%)')
    plt.title(f'Curtailment Curve for {example_ba}')
    plt.grid(True, alpha=0.3)
    
    # Add horizontal lines for reference curtailment limits
    for limit in curtailment_limits:
        plt.axhline(y=limit*100, color='red', linestyle='--', alpha=0.5, 
                   label=f'{limit*100:.2f}% limit')
    
    plt.legend()
    curve_file = viz_dir / f"curtailment_curve_{example_ba.replace(' ', '_')}.png"
    plt.savefig(curve_file, dpi=300, bbox_inches='tight')
    print(f"Curtailment curve saved to {curve_file}")

print("\nAnalysis complete!")