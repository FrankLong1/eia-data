"""Module for calculating curtailment-enabled headroom as described in the paper."""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from config import CURTAILMENT_PARAMS, OUTPUT_DIR

logger = logging.getLogger(__name__)


class CurtailmentAnalyzer:
    """Analyzes load data to calculate curtailment-enabled headroom."""
    
    def __init__(self, params: Dict = CURTAILMENT_PARAMS):
        """Initialize the curtailment analyzer with parameters."""
        self.params = params
    
    def calculate_peak_load(self, df: pd.DataFrame, ba_code: str, 
                           year: Optional[int] = None) -> float:
        """
        Calculate peak load for a BA, optionally for a specific year.
        
        Args:
            df: Load data DataFrame
            ba_code: Balancing authority code
            year: Optional year to filter
            
        Returns:
            Peak load in MW
        """
        ba_data = df[df["ba_code"] == ba_code].copy()
        
        if year:
            ba_data = ba_data[ba_data["timestamp"].dt.year == year]
        
        if ba_data.empty:
            logger.warning(f"No data found for {ba_code} in year {year}")
            return np.nan
        
        return ba_data["load_mw"].max()
    
    def calculate_percentile_load(self, df: pd.DataFrame, ba_code: str,
                                 percentile: float = 95,
                                 year: Optional[int] = None) -> float:
        """
        Calculate percentile load for a BA.
        
        Args:
            df: Load data DataFrame
            ba_code: Balancing authority code
            percentile: Percentile to calculate (0-100)
            year: Optional year to filter
            
        Returns:
            Percentile load in MW
        """
        ba_data = df[df["ba_code"] == ba_code].copy()
        
        if year:
            ba_data = ba_data[ba_data["timestamp"].dt.year == year]
        
        if ba_data.empty:
            logger.warning(f"No data found for {ba_code} in year {year}")
            return np.nan
        
        return ba_data["load_mw"].quantile(percentile / 100)
    
    def calculate_headroom(self, df: pd.DataFrame, ba_code: str,
                          reference_load: float) -> pd.DataFrame:
        """
        Calculate hourly headroom relative to a reference load.
        
        Args:
            df: Load data DataFrame
            ba_code: Balancing authority code
            reference_load: Reference load level (e.g., peak or percentile)
            
        Returns:
            DataFrame with headroom calculations
        """
        ba_data = df[df["ba_code"] == ba_code].copy()
        ba_data = ba_data.sort_values("timestamp")
        
        # Calculate headroom
        ba_data["headroom_mw"] = reference_load - ba_data["load_mw"]
        ba_data["headroom_percent"] = (ba_data["headroom_mw"] / reference_load) * 100
        
        # Apply minimum headroom constraint
        ba_data.loc[ba_data["headroom_mw"] < self.params["min_headroom_mw"], "headroom_mw"] = 0
        ba_data.loc[ba_data["headroom_percent"] < 0, "headroom_percent"] = 0
        
        return ba_data
    
    def calculate_curtailable_hours(self, headroom_df: pd.DataFrame,
                                   headroom_threshold_mw: float = 100) -> Dict:
        """
        Calculate statistics on curtailable hours.
        
        Args:
            headroom_df: DataFrame with headroom calculations
            headroom_threshold_mw: Minimum headroom to consider curtailable
            
        Returns:
            Dictionary with curtailment statistics
        """
        curtailable = headroom_df["headroom_mw"] >= headroom_threshold_mw
        
        stats = {
            "total_hours": len(headroom_df),
            "curtailable_hours": curtailable.sum(),
            "curtailable_percent": (curtailable.sum() / len(headroom_df)) * 100,
            "avg_headroom_mw": headroom_df["headroom_mw"].mean(),
            "max_headroom_mw": headroom_df["headroom_mw"].max(),
            "avg_curtailable_headroom_mw": headroom_df.loc[curtailable, "headroom_mw"].mean()
        }
        
        return stats
    
    def analyze_seasonal_patterns(self, df: pd.DataFrame, ba_code: str) -> pd.DataFrame:
        """
        Analyze seasonal patterns in load and headroom.
        
        Args:
            df: Load data DataFrame with headroom
            ba_code: Balancing authority code
            
        Returns:
            DataFrame with seasonal statistics
        """
        ba_data = df[df["ba_code"] == ba_code].copy()
        ba_data["month"] = ba_data["timestamp"].dt.month
        ba_data["hour"] = ba_data["timestamp"].dt.hour
        ba_data["season"] = ba_data["month"].map({
            12: "Winter", 1: "Winter", 2: "Winter",
            3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer",
            9: "Fall", 10: "Fall", 11: "Fall"
        })
        
        # Calculate seasonal statistics
        seasonal_stats = ba_data.groupby("season").agg({
            "load_mw": ["mean", "max", "std"],
            "headroom_mw": ["mean", "max", "std"],
            "headroom_percent": ["mean", "max"]
        }).round(2)
        
        # Calculate hourly patterns by season
        hourly_seasonal = ba_data.groupby(["season", "hour"]).agg({
            "load_mw": "mean",
            "headroom_mw": "mean"
        }).round(2)
        
        return seasonal_stats, hourly_seasonal
    
    def calculate_annual_trends(self, df: pd.DataFrame, ba_code: str) -> pd.DataFrame:
        """
        Calculate annual trends in peak load and headroom.
        
        Args:
            df: Load data DataFrame
            ba_code: Balancing authority code
            
        Returns:
            DataFrame with annual trends
        """
        ba_data = df[df["ba_code"] == ba_code].copy()
        ba_data["year"] = ba_data["timestamp"].dt.year
        
        annual_stats = []
        
        for year in ba_data["year"].unique():
            year_data = ba_data[ba_data["year"] == year]
            
            # Calculate annual statistics
            peak_load = year_data["load_mw"].max()
            avg_load = year_data["load_mw"].mean()
            p95_load = year_data["load_mw"].quantile(0.95)
            
            # Calculate headroom relative to annual peak
            year_data["headroom_from_peak"] = peak_load - year_data["load_mw"]
            
            stats = {
                "year": year,
                "peak_load_mw": peak_load,
                "avg_load_mw": avg_load,
                "p95_load_mw": p95_load,
                "load_factor": avg_load / peak_load,
                "avg_headroom_from_peak_mw": year_data["headroom_from_peak"].mean(),
                "hours_below_50pct_peak": (year_data["load_mw"] < peak_load * 0.5).sum()
            }
            
            annual_stats.append(stats)
        
        return pd.DataFrame(annual_stats)
    
    def analyze_curtailment_potential(self, df: pd.DataFrame, 
                                     save_results: bool = True) -> Dict:
        """
        Perform complete curtailment analysis for all BAs.
        
        Args:
            df: Cleaned load data DataFrame
            save_results: Whether to save analysis results
            
        Returns:
            Dictionary with analysis results for all BAs
        """
        logger.info("Starting curtailment potential analysis")
        
        results = {}
        all_headroom_data = []
        
        for ba_code in df["ba_code"].unique():
            logger.info(f"Analyzing {ba_code}")
            
            # Calculate reference loads
            peak_load = self.calculate_peak_load(df, ba_code)
            p95_load = self.calculate_percentile_load(
                df, ba_code, 
                percentile=self.params["percentile_threshold"]
            )
            
            # Calculate headroom from both peak and percentile
            headroom_from_peak = self.calculate_headroom(df, ba_code, peak_load)
            headroom_from_p95 = self.calculate_headroom(df, ba_code, p95_load)
            
            # Add additional columns
            headroom_from_peak["reference_type"] = "peak"
            headroom_from_peak["reference_load_mw"] = peak_load
            
            headroom_from_p95["reference_type"] = "p95"
            headroom_from_p95["reference_load_mw"] = p95_load
            
            # Calculate curtailment statistics
            curtail_stats_peak = self.calculate_curtailable_hours(headroom_from_peak)
            curtail_stats_p95 = self.calculate_curtailable_hours(headroom_from_p95)
            
            # Get seasonal patterns
            seasonal_stats, hourly_seasonal = self.analyze_seasonal_patterns(
                headroom_from_peak, ba_code
            )
            
            # Get annual trends
            annual_trends = self.calculate_annual_trends(df, ba_code)
            
            # Store results
            results[ba_code] = {
                "peak_load_mw": peak_load,
                "p95_load_mw": p95_load,
                "curtailment_stats_peak": curtail_stats_peak,
                "curtailment_stats_p95": curtail_stats_p95,
                "seasonal_stats": seasonal_stats,
                "annual_trends": annual_trends
            }
            
            # Combine headroom data
            all_headroom_data.extend([headroom_from_peak, headroom_from_p95])
        
        # Combine all headroom data
        all_headroom_df = pd.concat(all_headroom_data, ignore_index=True)
        
        # Save results
        if save_results:
            # Save detailed headroom data
            headroom_path = f"{OUTPUT_DIR}/headroom_analysis.csv"
            all_headroom_df.to_csv(headroom_path, index=False)
            logger.info(f"Saved headroom data to {headroom_path}")
            
            # Save summary statistics
            summary_data = []
            for ba_code, ba_results in results.items():
                summary_data.append({
                    "ba_code": ba_code,
                    "peak_load_mw": ba_results["peak_load_mw"],
                    "p95_load_mw": ba_results["p95_load_mw"],
                    "avg_headroom_from_peak_mw": ba_results["curtailment_stats_peak"]["avg_headroom_mw"],
                    "curtailable_hours_from_peak_pct": ba_results["curtailment_stats_peak"]["curtailable_percent"],
                    "avg_headroom_from_p95_mw": ba_results["curtailment_stats_p95"]["avg_headroom_mw"],
                    "curtailable_hours_from_p95_pct": ba_results["curtailment_stats_p95"]["curtailable_percent"]
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_path = f"{OUTPUT_DIR}/curtailment_summary.csv"
            summary_df.to_csv(summary_path, index=False)
            logger.info(f"Saved summary to {summary_path}")
            
            # Save annual trends
            for ba_code, ba_results in results.items():
                trends_path = f"{OUTPUT_DIR}/annual_trends_{ba_code}.csv"
                ba_results["annual_trends"].to_csv(trends_path, index=False)
        
        return results
    
    def generate_report(self, results: Dict) -> str:
        """
        Generate a text report summarizing curtailment analysis.
        
        Args:
            results: Analysis results dictionary
            
        Returns:
            Report text
        """
        report = ["Curtailment-Enabled Headroom Analysis Report"]
        report.append("=" * 50)
        report.append("")
        
        for ba_code, ba_results in results.items():
            report.append(f"\n{ba_code} Summary:")
            report.append("-" * 30)
            report.append(f"Peak Load: {ba_results['peak_load_mw']:,.0f} MW")
            report.append(f"95th Percentile Load: {ba_results['p95_load_mw']:,.0f} MW")
            
            peak_stats = ba_results["curtailment_stats_peak"]
            report.append(f"\nHeadroom from Peak:")
            report.append(f"  Average: {peak_stats['avg_headroom_mw']:,.0f} MW")
            report.append(f"  Maximum: {peak_stats['max_headroom_mw']:,.0f} MW")
            report.append(f"  Curtailable Hours: {peak_stats['curtailable_percent']:.1f}%")
            
            p95_stats = ba_results["curtailment_stats_p95"]
            report.append(f"\nHeadroom from 95th Percentile:")
            report.append(f"  Average: {p95_stats['avg_headroom_mw']:,.0f} MW")
            report.append(f"  Maximum: {p95_stats['max_headroom_mw']:,.0f} MW")
            report.append(f"  Curtailable Hours: {p95_stats['curtailable_percent']:.1f}%")
        
        return "\n".join(report)


def main():
    """Main function for testing the curtailment analyzer."""
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Load cleaned data
    cleaned_data_path = f"{OUTPUT_DIR}/../processed/cleaned_hourly_load_data.csv"
    
    if os.path.exists(cleaned_data_path):
        df = pd.read_csv(cleaned_data_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        analyzer = CurtailmentAnalyzer()
        results = analyzer.analyze_curtailment_potential(df)
        
        # Generate and print report
        report = analyzer.generate_report(results)
        print(report)
    else:
        print(f"Cleaned data file not found at {cleaned_data_path}")


if __name__ == "__main__":
    main()