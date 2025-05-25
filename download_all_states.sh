#!/bin/bash

# EIA Plant Data Download Script - State by State
# Downloads plant data for all US states from 2016-2025
# Files are saved as {PLANT_ID}_{YEAR}_generation.csv

# Array of all US state codes
states=(
    "AL" "AK" "AZ" "AR" "CA" "CO" "CT" "DE" "FL" "GA"
    "HI" "ID" "IL" "IN" "IA" "KS" "KY" "LA" "ME" "MD"
    "MA" "MI" "MN" "MS" "MO" "MT" "NE" "NV" "NH" "NJ"
    "NM" "NY" "NC" "ND" "OH" "OK" "OR" "PA" "RI" "SC"
    "SD" "TN" "TX" "UT" "VT" "VA" "WA" "WV" "WI" "WY"
)

# Configuration
START_YEAR=2016
END_YEAR=2025
BASE_DIR="/Users/franklong/CS-Projects/eia-data"
YEARS_RANGE=$((END_YEAR - START_YEAR + 1))

# Change to project directory
cd "$BASE_DIR"

echo "Starting state-by-state download of EIA plant data"
echo "Period: ${START_YEAR} to ${END_YEAR} (${YEARS_RANGE} years)"
echo "Total states to process: ${#states[@]}"
echo "Estimated total operations: ${#states[@]} states × ${YEARS_RANGE} years"
echo "----------------------------------------"

# Counter for progress
completed=0
total=${#states[@]}
failed_states=()

# Start timer
start_time=$(date +%s)

# Loop through each state
for state in "${states[@]}"; do
    completed=$((completed + 1))
    echo ""
    echo "[$completed/$total] Processing state: $state"
    echo "========================================="
    
    # Run the download command for this state
    python -m src.data_fetching.download_plant_data \
        --states "$state" \
        --start "$START_YEAR" \
        --end "$END_YEAR"
    
    # Check if the command was successful
    if [ $? -eq 0 ]; then
        echo "✓ Successfully completed $state"
    else
        echo "✗ Error processing $state (exit code: $?)"
        failed_states+=("$state")
        echo "  Continuing with next state..."
    fi
    
    # Small delay between states to be nice to the API
    sleep 2
done

# End timer
end_time=$(date +%s)
duration=$((end_time - start_time))
duration_min=$((duration / 60))
duration_sec=$((duration % 60))

echo ""
echo "========================================="
echo "Download process complete!"
echo "Time elapsed: ${duration_min} minutes ${duration_sec} seconds"
echo ""

# Count total files downloaded
file_count=$(find "$BASE_DIR/plant_data/raw" -name "*.csv" | wc -l)
echo "Total CSV files in plant_data/raw: $file_count"

# Show failed states if any
if [ ${#failed_states[@]} -gt 0 ]; then
    echo ""
    echo "Failed states (${#failed_states[@]} total):"
    for failed in "${failed_states[@]}"; do
        echo "  - $failed"
    done
    echo ""
    echo "You can retry failed states with:"
    echo "python -m src.data_fetching.download_plant_data --states ${failed_states[*]} --start $START_YEAR --end $END_YEAR"
else
    echo ""
    echo "✓ All states processed successfully!"
fi