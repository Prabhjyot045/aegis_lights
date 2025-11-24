#!/usr/bin/env python3
"""
Evaluation Script - Compare Control vs Experimental

This script compares the control baseline (no adaptation) against
the experimental run (with MAPE-K adaptation) by generating
average travel time vs. cycle graphs.

Usage:
    python plot_comparison.py --control baseline.csv --db aegis.db --output comparison.png
"""

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional
import csv

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComparisonPlotter:
    """Generate comparison plots between control and experimental runs."""
    
    def __init__(self, control_csv: str, db_path: str):
        """
        Initialize comparison plotter.
        
        Args:
            control_csv: Path to control baseline CSV file
            db_path: Path to SQLite database with experimental data
        """
        self.control_csv = control_csv
        self.db_path = db_path
        self.control_data = []
        self.experimental_data = []
    
    def load_control_data(self) -> None:
        """Load control baseline data from CSV."""
        logger.info(f"Loading control data from {self.control_csv}")
        
        try:
            with open(self.control_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.control_data.append({
                        'cycle': int(row['cycle']),
                        'elapsed_time': float(row['elapsed_time']),
                        'avg_travel_time': float(row['avg_travel_time'])
                    })
            
            logger.info(f"Loaded {len(self.control_data)} control data points")
            
        except FileNotFoundError:
            logger.error(f"Control CSV file not found: {self.control_csv}")
            raise
        except Exception as e:
            logger.error(f"Failed to load control data: {e}")
            raise
    
    def load_experimental_data(self) -> None:
        """Load experimental data from database."""
        logger.info(f"Loading experimental data from {self.db_path}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query performance_metrics table
            cursor.execute("""
                SELECT 
                    cycle_number as cycle,
                    timestamp,
                    avg_trip_time
                FROM performance_metrics
                ORDER BY cycle_number
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning("No experimental data found in database")
                conn.close()
                return
            
            # Convert to list of dicts
            start_time = rows[0]['timestamp']
            for row in rows:
                avg_time = row['avg_trip_time']
                # Handle None values
                if avg_time is None:
                    continue
                self.experimental_data.append({
                    'cycle': row['cycle'],
                    'elapsed_time': row['timestamp'] - start_time,
                    'avg_travel_time': float(avg_time)
                })
            
            conn.close()
            logger.info(f"Loaded {len(self.experimental_data)} experimental data points")
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load experimental data: {e}")
            raise
    
    def calculate_statistics(self, data: List[dict]) -> dict:
        """
        Calculate statistics for a dataset.
        
        Args:
            data: List of data points with avg_travel_time
            
        Returns:
            Dictionary with mean, std, min, max
        """
        if not data:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0}
        
        values = [d['avg_travel_time'] for d in data]
        return {
            'mean': np.mean(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'median': np.median(values)
        }
    
    def plot_comparison(self, output_file: str, window: Optional[int] = 10) -> None:
        """
        Generate comparison plot.
        
        Args:
            output_file: Path to save output PNG
            window: Moving average window size (None to disable)
        """
        if not self.control_data and not self.experimental_data:
            logger.error("No data to plot")
            return
        
        logger.info("Generating comparison plot")
        
        # Create figure with single plot (smoothed only)
        fig, ax = plt.subplots(1, 1, figsize=(14, 8))
        fig.suptitle('Traffic Control Comparison: Control vs MAPE-K Adaptation', 
                     fontsize=16, fontweight='bold')
        
        # Get data arrays
        if self.control_data:
            control_cycles = [d['cycle'] for d in self.control_data]
            control_times = [d['avg_travel_time'] for d in self.control_data]
        
        if self.experimental_data:
            exp_cycles = [d['cycle'] for d in self.experimental_data]
            exp_times = [d['avg_travel_time'] for d in self.experimental_data]
        
        # Plot smoothed moving average only
        if window and window > 1:
            if self.control_data and len(self.control_data) >= window:
                control_ma = np.convolve(control_times, 
                                        np.ones(window)/window, mode='valid')
                control_ma_cycles = control_cycles[window-1:]
                ax.plot(control_ma_cycles, control_ma,
                        label=f'Control (No Adaptation, MA-{window})',
                        color='#FF6B6B', linewidth=2.5, alpha=0.85)
            
            if self.experimental_data and len(self.experimental_data) >= window:
                exp_ma = np.convolve(exp_times,
                                    np.ones(window)/window, mode='valid')
                exp_ma_cycles = exp_cycles[window-1:]
                ax.plot(exp_ma_cycles, exp_ma,
                        label=f'Experimental (MAPE-K, MA-{window})',
                        color='#4ECDC4', linewidth=2.5, alpha=0.85)
            
            ax.set_xlabel('Cycle Number', fontsize=13, fontweight='bold')
            ax.set_ylabel('Average Travel Time (seconds)', fontsize=13, fontweight='bold')
            ax.set_title(f'Smoothed Average Travel Time Comparison (Moving Average, window={window})', 
                         fontsize=15, pad=20)
            ax.legend(loc='upper left', fontsize=12, framealpha=0.95)
            ax.grid(True, alpha=0.3, linestyle='--')
        
        # Calculate and display statistics
        control_stats = self.calculate_statistics(self.control_data)
        exp_stats = self.calculate_statistics(self.experimental_data)
        
        stats_text = (
            f"Control Stats:\n"
            f"  Mean: {control_stats['mean']:.2f}s\n"
            f"  Std: {control_stats['std']:.2f}s\n"
            f"  Min: {control_stats['min']:.2f}s\n"
            f"  Max: {control_stats['max']:.2f}s\n"
            f"  Median: {control_stats['median']:.2f}s\n"
            f"\n"
            f"Experimental Stats:\n"
            f"  Mean: {exp_stats['mean']:.2f}s\n"
            f"  Std: {exp_stats['std']:.2f}s\n"
            f"  Min: {exp_stats['min']:.2f}s\n"
            f"  Max: {exp_stats['max']:.2f}s\n"
            f"  Median: {exp_stats['median']:.2f}s\n"
        )
        
        if exp_stats['mean'] > 0:
            improvement = ((control_stats['mean'] - exp_stats['mean']) / 
                          control_stats['mean']) * 100
            stats_text += f"\nImprovement: {improvement:+.2f}%"
        
        # Add text box with statistics
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        fig.text(0.98, 0.5, stats_text, transform=fig.transFigure,
                fontsize=10, verticalalignment='center',
                bbox=props, ha='right', family='monospace')
        
        plt.tight_layout(rect=[0, 0, 0.85, 0.96])
        
        # Save figure
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        
        logger.info(f"Plot saved to {output_path}")
        
        # Print statistics to console
        logger.info("\n" + "="*60)
        logger.info("COMPARISON STATISTICS")
        logger.info("="*60)
        logger.info(stats_text)
        logger.info("="*60)
        
        plt.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Compare Control vs Experimental Traffic Control',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comparison
  python plot_comparison.py --control baseline.csv --db aegis.db --output comparison.png
  
  # Custom moving average window
  python plot_comparison.py --control baseline.csv --db aegis.db --output comparison.png --window 20
  
  # No smoothing
  python plot_comparison.py --control baseline.csv --db aegis.db --output comparison.png --window 0
        """
    )
    
    parser.add_argument(
        '--control',
        required=True,
        help='Path to control baseline CSV file'
    )
    
    parser.add_argument(
        '--db',
        required=True,
        help='Path to SQLite database with experimental data'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Output PNG file path'
    )
    
    parser.add_argument(
        '--window',
        type=int,
        default=10,
        help='Moving average window size (default: 10, 0 to disable)'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not Path(args.control).exists():
        logger.error(f"Control CSV file not found: {args.control}")
        return 1
    
    if not Path(args.db).exists():
        logger.error(f"Database file not found: {args.db}")
        return 1
    
    # Create plotter
    plotter = ComparisonPlotter(
        control_csv=args.control,
        db_path=args.db
    )
    
    # Load data
    plotter.load_control_data()
    plotter.load_experimental_data()
    
    # Generate plot
    window = args.window if args.window > 0 else None
    plotter.plot_comparison(args.output, window=window)
    
    logger.info("Comparison complete")
    return 0


if __name__ == '__main__':
    exit(main())
