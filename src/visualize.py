#!/usr/bin/env python3
"""
Visualization module for EIA curtailment analysis project.

This module provides comprehensive visualization functions for curtailment analysis results,
creating publication-ready plots that match the figures in the research paper.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import warnings
import logging
from datetime import datetime, timedelta

# Configure matplotlib for publication-quality plots
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 16

# Suppress warnings
warnings.filterwarnings('ignore')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Color palette for consistent visualizations
BA_COLORS = {
    'PJM': '#1f77b4',
    'MISO': '#ff7f0e', 
    'ERCOT': '#2ca02c',
    'SPP': '#d62728',
    'CAISO': '#9467bd',
    'ISO-NE': '#8c564b',
    'NYISO': '#e377c2',
    'SOCO': '#7f7f7f',
    'DEC': '#bcbd22',
    'DEP': '#17becf',
    'DEF': '#ff9896',
    'TVA': '#98df8a',
    'BPA': '#ffbb78',
    'AZPS': '#c5b0d5',
    'FPL': '#c49c94',
    'PACE': '#f7b6d3',
    'PACW': '#c7c7c7',
    'PGE': '#dbdb8d',
    'PSCO': '#9edae5',
    'SRP': '#393b79',
    'DESC': '#ad494a',
    'SCP': '#3182bd'
}

# Default color cycle for when BAs exceed predefined colors
DEFAULT_COLORS = plt.cm.Set3(np.linspace(0, 1, 12))


class CurtailmentVisualizer:
    """
    Publication-ready visualization suite for curtailment analysis results.
    
    This class creates all visualizations needed to understand and communicate
    curtailment analysis findings. Follows the visual style and conventions
    from the "Rethinking Load Growth" research paper.
    
    Key visualization types:
    - Curtailment headroom charts: Bar charts comparing load addition capacity
    - Load duration curves: Hourly demand patterns with headroom visualization  
    - Comparison matrices: Heatmaps of curtailment rates vs. load additions
    - Seasonal analysis: Summer/winter curtailment pattern breakdowns
    - Individual BA profiles: Deep-dive analysis for specific regions
    
    All plots use:
    - Consistent color schemes and styling
    - Publication-quality formatting (300 DPI)
    - Both PNG and PDF output formats
    - Descriptive titles, labels, and legends
    """
    
    def __init__(self, output_dir: Union[str, Path] = None):
        """
        Initialize the visualizer with output directory and logging setup.
        
        Sets up directory structure for organized plot output:
        - output_dir/plots/: Individual plot files
        - output_dir/reports/: Combined report documents (future)
        
        Args:
            output_dir: Base directory for saving all visualization outputs
                       If None, saves to current working directory
                       Typical usage: 'output/analysis_20240712_143022/'
        """
        # Set up output directory structure
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organized output
        self.plots_dir = self.output_dir / "plots"  # Individual plot files
        self.reports_dir = self.output_dir / "reports"  # Future: combined reports
        self.plots_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
    def _get_ba_color(self, ba: str) -> str:
        """Get consistent color for a balancing authority."""
        return BA_COLORS.get(ba, DEFAULT_COLORS[hash(ba) % len(DEFAULT_COLORS)])
    
    def _format_power_axis(self, ax, unit: str = 'MW'):
        """Format power axis with appropriate units and formatting."""
        if unit == 'GW':
            formatter = lambda x, p: f'{x:.1f}'
        else:
            formatter = lambda x, p: f'{x:,.0f}'
        ax.yaxis.set_major_formatter(plt.FuncFormatter(formatter))
        ax.set_ylabel(f'Power ({unit})')
        
    def _save_plot(self, fig, filename: str, dpi: int = 300):
        """Save plot with consistent formatting."""
        filepath = self.plots_dir / filename
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        self.logger.info(f"Saved plot: {filepath}")
        return filepath
    
    def create_load_duration_curve(self, 
                                 ba_data: pd.DataFrame,
                                 ba_name: str,
                                 show_seasonal_peaks: bool = True,
                                 figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Create a load duration curve for a specific balancing authority.
        
        Load duration curves show demand values sorted from highest to lowest,
        providing insights into system load patterns and peak demand frequency.
        
        Args:
            ba_data: DataFrame with 'Timestamp' and 'Demand' columns
            ba_name: Name of the balancing authority
            show_seasonal_peaks: Whether to show seasonal peak lines
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Sort demand values in descending order
        sorted_demand = ba_data['Demand'].sort_values(ascending=False).values
        hours = np.arange(1, len(sorted_demand) + 1)
        
        # Convert to percentage of year
        hours_pct = (hours / len(sorted_demand)) * 100
        
        # Plot load duration curve
        ax.plot(hours_pct, sorted_demand / 1000, color=self._get_ba_color(ba_name), 
                linewidth=2, label=f'{ba_name} Load Duration')
        
        # Add seasonal peaks if requested
        if show_seasonal_peaks:
            # Calculate seasonal peaks
            ba_data_temp = ba_data.copy()
            ba_data_temp['Month'] = pd.to_datetime(ba_data_temp['Timestamp']).dt.month
            
            # Summer peak (June-August)
            summer_data = ba_data_temp[ba_data_temp['Month'].isin([6, 7, 8])]
            summer_peak = summer_data['Demand'].max() / 1000 if not summer_data.empty else 0
            
            # Winter peak (December-February)
            winter_data = ba_data_temp[ba_data_temp['Month'].isin([12, 1, 2])]
            winter_peak = winter_data['Demand'].max() / 1000 if not winter_data.empty else 0
            
            # Add peak lines
            ax.axhline(y=summer_peak, color='red', linestyle='--', alpha=0.7, 
                      label=f'Summer Peak ({summer_peak:.1f} GW)')
            ax.axhline(y=winter_peak, color='blue', linestyle='--', alpha=0.7, 
                      label=f'Winter Peak ({winter_peak:.1f} GW)')
        
        # Formatting
        ax.set_xlabel('Hours of Year (%)')
        ax.set_ylabel('Demand (GW)')
        ax.set_title(f'Load Duration Curve - {ba_name}')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Set reasonable axis limits
        ax.set_xlim(0, 100)
        ax.set_ylim(0, max(sorted_demand) / 1000 * 1.1)
        
        return fig
    
    def create_curtailment_headroom_chart(self, 
                                        results_df: pd.DataFrame,
                                        curtailment_limit: float = 0.0025,
                                        unit: str = 'GW',
                                        figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Create a bar chart showing curtailment headroom across balancing authorities.
        
        Args:
            results_df: DataFrame with curtailment analysis results
            curtailment_limit: Curtailment limit to display (as fraction, e.g., 0.0025)
            unit: Unit for display ('MW' or 'GW')
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        # Filter for specific curtailment limit
        if 'Curtailment_Limit_%' in results_df.columns:
            limit_col = 'Curtailment_Limit_%'
            limit_val = curtailment_limit * 100
        elif 'Curtailment_Limit' in results_df.columns:
            limit_col = 'Curtailment_Limit'
            limit_val = curtailment_limit * 100
        else:
            # Try to find the column with curtailment limit data
            possible_cols = [col for col in results_df.columns if 'curtailment' in col.lower() and 'limit' in col.lower()]
            if possible_cols:
                limit_col = possible_cols[0]
                limit_val = curtailment_limit * 100
            else:
                raise ValueError("No curtailment limit column found in results DataFrame")
        
        filtered_df = results_df[results_df[limit_col] == limit_val].copy()
        
        if filtered_df.empty:
            raise ValueError(f"No data found for curtailment limit {limit_val}%")
        
        # Determine load column
        load_cols = [col for col in filtered_df.columns if 'load' in col.lower() and 'mw' in col.lower()]
        if not load_cols:
            raise ValueError("No load column found in results DataFrame")
        load_col = load_cols[0]
        
        # Sort by load capacity (descending)
        filtered_df = filtered_df.sort_values(load_col, ascending=False)
        
        # Convert units if needed
        if unit == 'GW':
            filtered_df['Load_Display'] = filtered_df[load_col] / 1000
        else:
            filtered_df['Load_Display'] = filtered_df[load_col]
        
        # Create bar chart
        fig, ax = plt.subplots(figsize=figsize)
        
        colors = [self._get_ba_color(ba) for ba in filtered_df['BA']]
        bars = ax.bar(filtered_df['BA'], filtered_df['Load_Display'], color=colors, alpha=0.8)
        
        # Add value labels on bars
        for bar, value in zip(bars, filtered_df['Load_Display']):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                   f'{value:.1f}', ha='center', va='bottom', fontweight='bold')
        
        # Formatting
        ax.set_xlabel('Balancing Authority')
        ax.set_ylabel(f'Maximum Additional Load ({unit})')
        ax.set_title(f'Curtailment-Enabled Headroom at {curtailment_limit*100:.2f}% Curtailment Limit')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Rotate x-axis labels for better readability
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        # Add total capacity annotation
        total_capacity = filtered_df['Load_Display'].sum()
        ax.text(0.02, 0.98, f'Total: {total_capacity:.1f} {unit}', 
                transform=ax.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        return fig
    
    def create_seasonal_curtailment_analysis(self, 
                                           ba_data: pd.DataFrame,
                                           ba_name: str,
                                           load_addition: float,
                                           figsize: Tuple[int, int] = (14, 8)) -> plt.Figure:
        """
        Create seasonal curtailment analysis showing monthly patterns.
        
        Args:
            ba_data: DataFrame with 'Timestamp' and 'Demand' columns
            ba_name: Name of the balancing authority
            load_addition: Additional load in MW
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
        
        # Prepare data
        ba_data_temp = ba_data.copy()
        ba_data_temp['Timestamp'] = pd.to_datetime(ba_data_temp['Timestamp'])
        ba_data_temp['Month'] = ba_data_temp['Timestamp'].dt.month
        ba_data_temp['Hour'] = ba_data_temp['Timestamp'].dt.hour
        ba_data_temp['DayOfYear'] = ba_data_temp['Timestamp'].dt.dayofyear
        
        # Calculate seasonal peaks
        summer_peak = ba_data_temp[ba_data_temp['Month'].isin([6, 7, 8])]['Demand'].max()
        winter_peak = ba_data_temp[ba_data_temp['Month'].isin([12, 1, 2])]['Demand'].max()
        
        # Determine seasonal threshold for each hour
        ba_data_temp['Seasonal_Threshold'] = ba_data_temp['Month'].apply(
            lambda m: summer_peak if 4 <= m <= 10 else winter_peak
        )
        
        # Calculate curtailment with load addition
        ba_data_temp['Augmented_Demand'] = ba_data_temp['Demand'] + load_addition
        ba_data_temp['Curtailment'] = np.maximum(0, ba_data_temp['Augmented_Demand'] - ba_data_temp['Seasonal_Threshold'])
        ba_data_temp['Curtailment_Rate'] = ba_data_temp['Curtailment'] / load_addition
        
        # Plot 1: Monthly curtailment patterns
        monthly_curtailment = ba_data_temp.groupby('Month')['Curtailment'].sum() / 1000  # Convert to GWh
        ax1.bar(monthly_curtailment.index, monthly_curtailment.values, 
                color=self._get_ba_color(ba_name), alpha=0.7)
        ax1.set_xlabel('Month')
        ax1.set_ylabel('Monthly Curtailment (GWh)')
        ax1.set_title(f'Monthly Curtailment - {ba_name}')
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(range(1, 13))
        
        # Plot 2: Hourly curtailment patterns
        hourly_curtailment = ba_data_temp.groupby('Hour')['Curtailment_Rate'].mean() * 100
        ax2.plot(hourly_curtailment.index, hourly_curtailment.values, 
                color=self._get_ba_color(ba_name), linewidth=2, marker='o', markersize=3)
        ax2.set_xlabel('Hour of Day')
        ax2.set_ylabel('Average Curtailment Rate (%)')
        ax2.set_title(f'Hourly Curtailment Pattern - {ba_name}')
        ax2.grid(True, alpha=0.3)
        ax2.set_xticks(range(0, 24, 3))
        
        # Plot 3: Seasonal load and threshold comparison
        seasonal_stats = ba_data_temp.groupby('Month').agg({
            'Demand': 'mean',
            'Seasonal_Threshold': 'first',
            'Augmented_Demand': 'mean'
        }) / 1000  # Convert to GW
        
        ax3.plot(seasonal_stats.index, seasonal_stats['Demand'], 
                label='Original Demand', color='blue', linewidth=2)
        ax3.plot(seasonal_stats.index, seasonal_stats['Augmented_Demand'], 
                label='With Additional Load', color='red', linewidth=2)
        ax3.plot(seasonal_stats.index, seasonal_stats['Seasonal_Threshold'], 
                label='Seasonal Threshold', color='green', linewidth=2, linestyle='--')
        ax3.set_xlabel('Month')
        ax3.set_ylabel('Average Demand (GW)')
        ax3.set_title(f'Seasonal Demand Profile - {ba_name}')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        ax3.set_xticks(range(1, 13))
        
        # Plot 4: Curtailment duration analysis
        # Calculate consecutive curtailment events
        ba_data_temp['Curtailed'] = ba_data_temp['Curtailment'] > 0
        ba_data_temp['Event_Group'] = (ba_data_temp['Curtailed'] != ba_data_temp['Curtailed'].shift()).cumsum()
        
        # Get duration of each curtailment event
        curtailment_events = ba_data_temp[ba_data_temp['Curtailed']].groupby('Event_Group').size()
        
        if len(curtailment_events) > 0:
            ax4.hist(curtailment_events.values, bins=20, alpha=0.7, 
                    color=self._get_ba_color(ba_name), edgecolor='black')
            ax4.set_xlabel('Curtailment Event Duration (hours)')
            ax4.set_ylabel('Number of Events')
            ax4.set_title(f'Curtailment Event Duration Distribution - {ba_name}')
            ax4.grid(True, alpha=0.3)
            
            # Add statistics
            avg_duration = curtailment_events.mean()
            ax4.axvline(avg_duration, color='red', linestyle='--', 
                       label=f'Average: {avg_duration:.1f} hours')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No curtailment events', transform=ax4.transAxes, 
                    ha='center', va='center', fontsize=14)
            ax4.set_title(f'Curtailment Event Duration - {ba_name}')
        
        plt.tight_layout()
        return fig
    
    def create_load_factor_headroom_scatter(self, 
                                          results_df: pd.DataFrame,
                                          ba_demand_stats: pd.DataFrame,
                                          curtailment_limit: float = 0.0025,
                                          figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create scatter plot of load factor vs curtailment headroom.
        
        Args:
            results_df: DataFrame with curtailment analysis results
            ba_demand_stats: DataFrame with BA statistics including load factor
            curtailment_limit: Curtailment limit to display
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        # Filter for specific curtailment limit
        if 'Curtailment_Limit_%' in results_df.columns:
            limit_col = 'Curtailment_Limit_%'
            limit_val = curtailment_limit * 100
        elif 'Curtailment_Limit' in results_df.columns:
            limit_col = 'Curtailment_Limit'
            limit_val = curtailment_limit * 100
        else:
            limit_col = [col for col in results_df.columns if 'curtailment' in col.lower() and 'limit' in col.lower()][0]
            limit_val = curtailment_limit * 100
        
        filtered_df = results_df[results_df[limit_col] == limit_val].copy()
        
        # Merge with demand statistics
        merged_df = filtered_df.merge(ba_demand_stats, left_on='BA', right_index=True, how='inner')
        
        # Create scatter plot
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot points
        for idx, row in merged_df.iterrows():
            ax.scatter(row['Load_Factor'], row['Max_Load_Addition_GW'], 
                      s=100, color=self._get_ba_color(row['BA']), alpha=0.7, 
                      edgecolors='black', linewidth=0.5)
            
            # Add BA labels
            ax.annotate(row['BA'], (row['Load_Factor'], row['Max_Load_Addition_GW']), 
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Add trend line
        if len(merged_df) > 1:
            z = np.polyfit(merged_df['Load_Factor'], merged_df['Max_Load_Addition_GW'], 1)
            p = np.poly1d(z)
            ax.plot(merged_df['Load_Factor'].sort_values(), 
                   p(merged_df['Load_Factor'].sort_values()), 
                   "r--", alpha=0.8, linewidth=2, label=f'Trend (R²={np.corrcoef(merged_df["Load_Factor"], merged_df["Max_Load_Addition_GW"])[0,1]**2:.3f})')
        
        # Formatting
        ax.set_xlabel('Load Factor')
        ax.set_ylabel('Maximum Additional Load (GW)')
        ax.set_title(f'Load Factor vs Curtailment Headroom\n({curtailment_limit*100:.2f}% Curtailment Limit)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        return fig
    
    def create_curtailment_comparison_matrix(self, 
                                           results_df: pd.DataFrame,
                                           figsize: Tuple[int, int] = (12, 10)) -> plt.Figure:
        """
        Create a heatmap matrix comparing curtailment limits across BAs.
        
        Args:
            results_df: DataFrame with curtailment analysis results
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        # Pivot the data to create a matrix
        if 'Curtailment_Limit_%' in results_df.columns:
            limit_col = 'Curtailment_Limit_%'
        elif 'Curtailment_Limit' in results_df.columns:
            limit_col = 'Curtailment_Limit'
        else:
            limit_col = [col for col in results_df.columns if 'curtailment' in col.lower() and 'limit' in col.lower()][0]
        
        # Find the GW load column
        load_col = [col for col in results_df.columns if 'gw' in col.lower() and 'load' in col.lower()]
        if not load_col:
            # Convert MW to GW
            mw_col = [col for col in results_df.columns if 'mw' in col.lower() and 'load' in col.lower()][0]
            results_df['Load_GW'] = results_df[mw_col] / 1000
            load_col = 'Load_GW'
        else:
            load_col = load_col[0]
        
        matrix_df = results_df.pivot(index='BA', columns=limit_col, values=load_col)
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create custom colormap
        cmap = plt.cm.YlOrRd
        
        # Create heatmap
        im = ax.imshow(matrix_df.values, cmap=cmap, aspect='auto')
        
        # Set ticks and labels
        ax.set_xticks(range(len(matrix_df.columns)))
        ax.set_yticks(range(len(matrix_df.index)))
        ax.set_xticklabels([f'{col:.2f}%' for col in matrix_df.columns])
        ax.set_yticklabels(matrix_df.index)
        
        # Add text annotations
        for i in range(len(matrix_df.index)):
            for j in range(len(matrix_df.columns)):
                value = matrix_df.iloc[i, j]
                if not np.isnan(value):
                    text = ax.text(j, i, f'{value:.1f}', ha='center', va='center', 
                                 color='white' if value > matrix_df.values.max() * 0.5 else 'black',
                                 fontweight='bold', fontsize=9)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.6)
        cbar.set_label('Maximum Additional Load (GW)', rotation=270, labelpad=20)
        
        # Formatting
        ax.set_xlabel('Curtailment Limit (%)')
        ax.set_ylabel('Balancing Authority')
        ax.set_title('Curtailment Headroom Comparison Matrix')
        
        return fig
    
    def create_comprehensive_report(self, 
                                  results_df: pd.DataFrame,
                                  ba_data_dict: Dict[str, pd.DataFrame],
                                  ba_demand_stats: Optional[pd.DataFrame] = None) -> Dict[str, Path]:
        """
        Create a comprehensive visualization report with all key publication-ready plots.
        
        This is the main entry point for generating the complete set of visualizations
        that accompany the curtailment analysis. Creates multiple plot types:
        
        1. Curtailment headroom bar charts - comparing load addition capacity across BAs
        2. Comparison matrices - heatmaps showing curtailment rates vs. load additions
        3. Load duration curves - showing top BAs' demand patterns and headroom
        4. Seasonal analysis plots - summer vs winter curtailment patterns
        5. Individual BA deep-dive plots - detailed analysis for specific regions
        
        All plots use consistent styling, colors, and formatting for publication quality.
        Plots are saved to timestamped output directory with both PNG and PDF formats.
        
        Args:
            results_df: Curtailment analysis results with columns like 'BA', 'Max_Load_Addition_GW', 
                       'Curtailment_Rate', etc. (output from CurtailmentAnalyzer)
            ba_data_dict: Dictionary mapping BA names to their hourly demand DataFrames
                         Used for load duration curves and demand pattern analysis
            ba_demand_stats: Optional pre-computed demand statistics (currently unused)
            
        Returns:
            Dictionary mapping plot type names to their saved file paths
            e.g., {'headroom_chart': Path('output/plots/headroom.png'), ...}
        """
        plot_files = {}
        
        self.logger.info("Creating comprehensive visualization report...")
        
        # 1. CURTAILMENT HEADROOM BAR CHART
        # Shows maximum load addition (GW) for each BA at different curtailment rates
        # Key plot for comparing BA capacity across regions
        try:
            fig = self.create_curtailment_headroom_chart(results_df)
            plot_files['headroom_chart'] = self._save_plot(fig, 'curtailment_headroom_chart.png')
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error creating headroom chart: {e}")
        
        # 2. CURTAILMENT COMPARISON MATRIX  
        # Heatmap showing curtailment rates vs load additions across BAs
        # Useful for identifying optimal operating points
        try:
            fig = self.create_curtailment_comparison_matrix(results_df)
            plot_files['comparison_matrix'] = self._save_plot(fig, 'curtailment_comparison_matrix.png')
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error creating comparison matrix: {e}")
        
        # 3. Load duration curves for top BAs
        top_bas = results_df.groupby('BA')['Max_Load_Addition_GW'].max().sort_values(ascending=False).head(6).index
        
        for ba in top_bas:
            if ba in ba_data_dict:
                try:
                    fig = self.create_load_duration_curve(ba_data_dict[ba], ba)
                    plot_files[f'load_duration_{ba}'] = self._save_plot(fig, f'load_duration_curve_{ba}.png')
                    plt.close(fig)
                except Exception as e:
                    self.logger.error(f"Error creating load duration curve for {ba}: {e}")
        
        # 4. Seasonal analysis for top BAs
        for ba in top_bas[:3]:  # Top 3 BAs only
            if ba in ba_data_dict:
                try:
                    # Use median load addition for seasonal analysis
                    ba_results = results_df[results_df['BA'] == ba]
                    if not ba_results.empty:
                        load_addition = ba_results['Max_Load_Addition_MW'].median()
                        fig = self.create_seasonal_curtailment_analysis(ba_data_dict[ba], ba, load_addition)
                        plot_files[f'seasonal_{ba}'] = self._save_plot(fig, f'seasonal_analysis_{ba}.png')
                        plt.close(fig)
                except Exception as e:
                    self.logger.error(f"Error creating seasonal analysis for {ba}: {e}")
        
        # 5. Load factor scatter plot (if statistics available)
        if ba_demand_stats is not None:
            try:
                fig = self.create_load_factor_headroom_scatter(results_df, ba_demand_stats)
                plot_files['load_factor_scatter'] = self._save_plot(fig, 'load_factor_headroom_scatter.png')
                plt.close(fig)
            except Exception as e:
                self.logger.error(f"Error creating load factor scatter: {e}")
        
        self.logger.info(f"Created {len(plot_files)} visualization plots")
        return plot_files
    
    def create_summary_dashboard(self, 
                               results_df: pd.DataFrame,
                               ba_data_dict: Dict[str, pd.DataFrame],
                               figsize: Tuple[int, int] = (16, 12)) -> plt.Figure:
        """
        Create a summary dashboard with key metrics and visualizations.
        
        Args:
            results_df: DataFrame with curtailment analysis results
            ba_data_dict: Dictionary mapping BA names to their demand data
            figsize: Figure size as (width, height)
            
        Returns:
            matplotlib Figure object
        """
        fig = plt.figure(figsize=figsize)
        
        # Create a grid layout
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Total headroom by curtailment limit (top left)
        ax1 = fig.add_subplot(gs[0, 0])
        total_headroom = results_df.groupby('Curtailment_Limit_%')['Max_Load_Addition_GW'].sum()
        ax1.bar(total_headroom.index, total_headroom.values, color='steelblue', alpha=0.7)
        ax1.set_xlabel('Curtailment Limit (%)')
        ax1.set_ylabel('Total Headroom (GW)')
        ax1.set_title('Total System Headroom')
        ax1.grid(True, alpha=0.3)
        
        # 2. Number of BAs analyzed (top middle)
        ax2 = fig.add_subplot(gs[0, 1])
        ba_count = results_df.groupby('Curtailment_Limit_%')['BA'].nunique()
        ax2.bar(ba_count.index, ba_count.values, color='darkgreen', alpha=0.7)
        ax2.set_xlabel('Curtailment Limit (%)')
        ax2.set_ylabel('Number of BAs')
        ax2.set_title('BAs Analyzed')
        ax2.grid(True, alpha=0.3)
        
        # 3. Top 5 BAs by headroom (top right)
        ax3 = fig.add_subplot(gs[0, 2])
        top_5_results = results_df[results_df['Curtailment_Limit_%'] == 0.25].nlargest(5, 'Max_Load_Addition_GW')
        colors = [self._get_ba_color(ba) for ba in top_5_results['BA']]
        ax3.barh(top_5_results['BA'], top_5_results['Max_Load_Addition_GW'], color=colors, alpha=0.7)
        ax3.set_xlabel('Headroom (GW)')
        ax3.set_title('Top 5 BAs (0.25% Limit)')
        ax3.grid(True, alpha=0.3)
        
        # 4. Load duration curve for largest BA (middle left)
        ax4 = fig.add_subplot(gs[1, :2])
        largest_ba = results_df.groupby('BA')['Max_Load_Addition_GW'].max().idxmax()
        if largest_ba in ba_data_dict:
            ba_data = ba_data_dict[largest_ba]
            sorted_demand = ba_data['Demand'].sort_values(ascending=False).values
            hours_pct = np.linspace(0, 100, len(sorted_demand))
            ax4.plot(hours_pct, sorted_demand / 1000, color=self._get_ba_color(largest_ba), linewidth=2)
            ax4.set_xlabel('Hours of Year (%)')
            ax4.set_ylabel('Demand (GW)')
            ax4.set_title(f'Load Duration Curve - {largest_ba}')
            ax4.grid(True, alpha=0.3)
        
        # 5. Headroom distribution (middle right)
        ax5 = fig.add_subplot(gs[1, 2])
        headroom_data = results_df[results_df['Curtailment_Limit_%'] == 0.25]['Max_Load_Addition_GW']
        ax5.hist(headroom_data, bins=10, color='purple', alpha=0.7, edgecolor='black')
        ax5.set_xlabel('Headroom (GW)')
        ax5.set_ylabel('Number of BAs')
        ax5.set_title('Headroom Distribution\n(0.25% Limit)')
        ax5.grid(True, alpha=0.3)
        
        # 6. Summary statistics table (bottom)
        ax6 = fig.add_subplot(gs[2, :])
        ax6.axis('tight')
        ax6.axis('off')
        
        # Create summary statistics
        summary_stats = []
        for limit in sorted(results_df['Curtailment_Limit_%'].unique()):
            limit_data = results_df[results_df['Curtailment_Limit_%'] == limit]
            summary_stats.append([
                f'{limit:.2f}%',
                f'{limit_data["Max_Load_Addition_GW"].sum():.1f} GW',
                f'{limit_data["Max_Load_Addition_GW"].mean():.1f} GW',
                f'{limit_data["Max_Load_Addition_GW"].std():.1f} GW',
                f'{len(limit_data)} BAs'
            ])
        
        table = ax6.table(cellText=summary_stats,
                         colLabels=['Curtailment Limit', 'Total Headroom', 'Mean Headroom', 'Std Dev', 'BAs Analyzed'],
                         cellLoc='center',
                         loc='center',
                         colWidths=[0.15, 0.2, 0.2, 0.2, 0.15])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        
        # Style the table
        for i in range(len(summary_stats) + 1):
            for j in range(5):
                cell = table[(i, j)]
                if i == 0:  # Header row
                    cell.set_facecolor('#4CAF50')
                    cell.set_text_props(weight='bold', color='white')
                else:
                    cell.set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')
        
        plt.suptitle('EIA Curtailment Analysis Summary Dashboard', fontsize=20, fontweight='bold')
        
        return fig


def calculate_ba_demand_statistics(ba_data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Calculate demand statistics for each balancing authority.
    
    Args:
        ba_data_dict: Dictionary mapping BA names to their demand data
        
    Returns:
        DataFrame with demand statistics for each BA
    """
    stats_list = []
    
    for ba, data in ba_data_dict.items():
        if 'Demand' in data.columns:
            demand = data['Demand']
            
            # Calculate statistics
            avg_demand = demand.mean()
            peak_demand = demand.max()
            min_demand = demand.min()
            load_factor = avg_demand / peak_demand if peak_demand > 0 else 0
            
            stats_list.append({
                'BA': ba,
                'Average_Demand_MW': avg_demand,
                'Peak_Demand_MW': peak_demand,
                'Min_Demand_MW': min_demand,
                'Load_Factor': load_factor,
                'Data_Points': len(demand)
            })
    
    return pd.DataFrame(stats_list).set_index('BA')


# Example usage and testing functions
def main():
    """Example usage of the visualization module."""
    
    # Example data paths (adjust as needed)
    project_root = Path(__file__).parent.parent
    cleaned_data_dir = project_root / "ba_aggregate_data" / "cleaned"
    viz_dir = project_root / "ba_aggregate_data" / "visualizations"
    
    # Initialize visualizer
    visualizer = CurtailmentVisualizer(output_dir=viz_dir)
    
    # Example: Create a simple visualization
    print("EIA Curtailment Analysis Visualization Module")
    print("=" * 50)
    print(f"Output directory: {visualizer.output_dir}")
    print(f"Plots will be saved to: {visualizer.plots_dir}")
    
    # You would typically load your actual data here
    # For demonstration, we'll show how to use the functions
    
    print("\nVisualization functions available:")
    print("1. create_load_duration_curve()")
    print("2. create_curtailment_headroom_chart()")
    print("3. create_seasonal_curtailment_analysis()")
    print("4. create_load_factor_headroom_scatter()")
    print("5. create_curtailment_comparison_matrix()")
    print("6. create_comprehensive_report()")
    print("7. create_summary_dashboard()")
    
    print("\nTo use this module:")
    print("1. Load your curtailment analysis results")
    print("2. Load your BA demand data")
    print("3. Call the appropriate visualization functions")
    print("4. All plots will be saved to the specified output directory")


if __name__ == "__main__":
    main()