### Data Cleaner Module

This module is designed to clean hourly electricity load data, particularly from EIA (U.S. Energy Information Administration) sources. The cleaning process is largely based on the steps outlined in Appendix B of the "Rethinking Load Growth" paper by Satchwell et al. (2024). It aims to normalize data formats and handle common outliers found in energy consumption datasets.

### Main Function: `clean_eia_data`

The `clean_eia_data` function serves as the primary interface for the data cleaning pipeline. It orchestrates a series of normalization and outlier handling steps to process a raw pandas DataFrame.

#### Parameters:

The key parameters for `clean_eia_data` are:

*   `df_raw` (pd.DataFrame): The raw input DataFrame containing the electricity load data.
*   `datetime_col` (str, default='Timestamp'): The name of the column containing date-time information. This column will be converted to pandas datetime objects.
*   `demand_col_primary` (str, default='Demand'): The name of the primary column representing electricity demand.
*   `adj_demand_col_name` (str, default='Adjusted demand'): The name of the column representing adjusted demand. If available and non-null, values from this column are prioritized over `demand_col_primary`.
*   `ba_col` (str, default='Balancing Authority'): The name of the column containing Balancing Authority (BA) labels.
*   `interp_cols_user` (list[str], optional): A list of column names on which to perform linear interpolation for missing values and zeros. Defaults to `['Unified Demand']`.
*   `low_outlier_threshold_factor` (float, default=0.1): The factor (of the mean demand per BA) used to identify and impute low outliers. Values below `mean * factor` are considered outliers.
*   `spike_window_size` (int, default=3): The rolling window size used for identifying and correcting demand spikes.
*   `spike_threshold_factor` (float, default=3.0): The number of standard deviations from the rolling mean to identify a demand spike.
*   `peak_threshold_factor` (float, default=2.0): The factor used to identify erroneous peaks. Values greater than `historical_max_in_group * factor` are considered peaks. Note: the "historical_max_in_group" is determined from the current dataset passed to the function.
*   `perform_validation` (bool, default=False): If `True`, enables detailed logging of the cleaning process, including counts of corrected values and summary statistics for the cleaned demand data.

#### Returns:

*   `pd.DataFrame`: A pandas DataFrame with the cleaning steps applied. The primary output is the "Unified Demand" column, which contains the cleaned load data.

### Cleaning Steps:

The `clean_eia_data` function applies the following operations in sequence:

1.  **Normalization**:
    *   **Datetime conversion**: Converts the specified `datetime_col` to pandas `datetime64[ns]` objects.
    *   **Selection of demand values**: Creates a "Unified Demand" column by selecting values from `adj_demand_col_name` (if available and non-null) or `demand_col_primary`.
    *   **Balancing Authority (BA) label mapping**: Standardizes BA labels in the `ba_col` to a common set of acronyms (e.g., "CPLE" to "DEP").

2.  **Outlier Handling** (performed on the "Unified Demand" column):
    *   **Fill missing values and zeros**: Replaces `NaN` values and zeros in the specified columns (typically "Unified Demand") using linear interpolation.
    *   **Impute low outliers**: For each BA, identifies demand values below a threshold (defined by `low_outlier_threshold_factor` times the BA's mean demand) and imputes them using forward-fill then backward-fill from neighboring non-outlier values within the same BA. Requires a sorted datetime column.
    *   **Correct demand spikes**: Identifies and corrects demand spikes by comparing values to a rolling mean +/- a number of rolling standard deviations (defined by `spike_window_size` and `spike_threshold_factor`). This can be done per BA (if `ba_col` is provided and valid) or globally. Spikes are replaced with the rolling mean.
    *   **Handle erroneous peaks**: For each BA, flags values that exceed a dynamic threshold (defined by `peak_threshold_factor` times the maximum demand observed for that BA *in the current dataset*) and replaces them using linear interpolation.

3.  **Validation Logging**:
    *   If `perform_validation` is set to `True`, the function logs detailed information about the cleaning process. This includes:
        *   Confirmation of normalization steps.
        *   Approximate counts of missing/zero values filled.
        *   Approximate counts of low outliers imputed.
        *   Approximate counts of demand spikes corrected.
        *   Approximate counts of erroneous peaks handled.
        *   Summary statistics (min, max, mean, median, count) for the "Unified Demand" column, usually per BA.

### Example Usage (Conceptual):

```python
import pandas as pd
# Assuming your data_cleaner module is structured under 'src'
# Adjust the import path based on your project structure and how you run your code.
# For example, if running from the root of the project:
from src.data_cleaning.DataCleaner import clean_eia_data

# Example: Load a raw DataFrame (replace with your actual data loading)
# raw_df = pd.read_csv('your_eia_data.csv') 

# Placeholder for raw_df for the example to be runnable conceptually
raw_df_data = {
    'timestamp': ['2023-01-01 00:00:00', '2023-01-01 01:00:00', '2023-01-01 02:00:00'],
    'load_mw': [100, 110, 0], # Example with a zero value
    'ba_code': ['BPA', 'BPA', 'BPA']
}
raw_df = pd.DataFrame(raw_df_data)

# Apply the cleaning function
# cleaned_df = clean_eia_data(
#     df_raw=raw_df,
#     datetime_col='timestamp',         # Specify your actual datetime column name
#     demand_col_primary='load_mw',     # Specify your actual demand column name
#     adj_demand_col_name=None,         # Set to None or your column name if it exists
#     ba_col='ba_code',                 # Specify your actual BA column name
#     perform_validation=True           # Enable detailed logging
# )

# print(cleaned_df.head())
```
