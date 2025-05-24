#!/usr/bin/env python3
"""
Summarize plant data organized by state.
"""

import pandas as pd
from pathlib import Path
import json

def summarize_state_organized_data(data_dir="plant_data/raw_by_state"):
    """
    Create a summary of plant data organized by state.
    """
    data_path = Path(data_dir)
    
    summary = {}
    
    # Iterate through states
    for state_dir in sorted(data_path.iterdir()):
        if not state_dir.is_dir():
            continue
            
        state = state_dir.name
        plants = []
        
        # Iterate through CSV files in each state directory
        for csv_file in sorted(state_dir.glob("*generation*.csv")):
            if not csv_file.is_file():
                continue
                
            # Extract plant ID from filename (e.g., "260_generation_2023-01_2023-12.csv" -> "260")
            plant_id = csv_file.name.split('_')[0]
            
            # Read the file to get plant info
            df = pd.read_csv(csv_file)
            if not df.empty:
                # Get plant name from the first row with ALL fuel type
                all_rows = df[df['fuel2002'] == 'ALL']
                if not all_rows.empty:
                    plant_name = all_rows.iloc[0]['plantName']
                    total_gen = all_rows['generation'].sum()
                    
                    # Extract date range from filename
                    parts = csv_file.stem.split('_')
                    if len(parts) >= 4:
                        start_date = parts[2]
                        end_date = parts[3]
                        date_range = f"{start_date} to {end_date}"
                    else:
                        date_range = "Unknown"
                    
                    plants.append({
                        'id': plant_id,
                        'name': plant_name,
                        'total_generation_mwh': float(total_gen),
                        'months_with_data': int(len(all_rows)),
                        'date_range': date_range,
                        'filename': csv_file.name
                    })
        
        summary[state] = {
            'plant_count': len(plants),
            'plants': sorted(plants, key=lambda x: x['total_generation_mwh'], reverse=True)
        }
    
    return summary


def print_summary(summary):
    """
    Print a formatted summary of the data.
    """
    print("\n" + "="*60)
    print("PLANT DATA SUMMARY BY STATE")
    print("="*60)
    
    total_plants = sum(state_data['plant_count'] for state_data in summary.values())
    print(f"\nTotal States: {len(summary)}")
    print(f"Total Plants: {total_plants}")
    
    for state in sorted(summary.keys()):
        state_data = summary[state]
        print(f"\n{state} - {state_data['plant_count']} plants:")
        print("-" * 40)
        
        # Show top 5 plants by generation
        for i, plant in enumerate(state_data['plants'][:5]):
            print(f"  {i+1}. {plant['name']} (ID: {plant['id']})")
            print(f"     Total Generation: {plant['total_generation_mwh']:,.0f} MWh")
            print(f"     Months of Data: {plant['months_with_data']}")
        
        if state_data['plant_count'] > 5:
            print(f"  ... and {state_data['plant_count'] - 5} more plants")
    
    print("\n" + "="*60)
    print("DATA ORGANIZATION:")
    print("  plant_data/raw_by_state/")
    print("    ├── CA/                              # California")
    print("    │   ├── 260_generation_2023-01_2023-12.csv")
    print("    │   ├── 286_generation_2023-01_2023-12.csv") 
    print("    │   └── ...")
    print("    └── TX/                              # Texas")
    print("        ├── 3470_generation_2023-01_2023-12.csv")
    print("        ├── 6145_generation_2023-01_2023-12.csv")
    print("        └── ...")
    print("="*60)


def save_summary_json(summary, output_file="plant_data/raw_by_state/summary.json"):
    """
    Save summary as JSON file.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to: {output_file}")


if __name__ == "__main__":
    # Create summary
    summary = summarize_state_organized_data()
    
    # Print summary
    print_summary(summary)
    
    # Save as JSON
    save_summary_json(summary)