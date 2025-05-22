import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Load PJM data
df = pd.read_csv('data/raw/PJM_hourly_demand.csv')

# Convert period to datetime
df['datetime'] = pd.to_datetime(df['period'])

# Create the plot
plt.figure(figsize=(15, 8))
plt.plot(df['datetime'], df['value'], linewidth=1)

# Format the plot
plt.title('PJM Hourly Electricity Demand (Oct-Dec 2023)', fontsize=16)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Demand (MWh)', fontsize=12)

# Format x-axis
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
plt.gca().xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=45)

# Add grid
plt.grid(True, alpha=0.3)

# Tight layout and save
plt.tight_layout()
plt.savefig('data/visualizations/PJM_hourly_demand.png', dpi=300, bbox_inches='tight')
plt.show()

print(f"Plotted {len(df)} hours of PJM demand data")
print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
print(f"Demand range: {df['value'].min():.0f} - {df['value'].max():.0f} MWh")