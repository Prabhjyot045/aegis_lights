#!/usr/bin/env python3
"""
Control Baseline Script - No Adaptation

This script monitors the simulator WITHOUT making any adaptations.
It only collects average travel time data every 5 seconds for comparison
with the adaptive controller.

Usage:
    python control_baseline.py --duration 300 --output baseline_data.csv
"""

import time
import logging
import argparse
import csv
from pathlib import Path
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ControlBaseline:
    """Monitor simulator without making adaptations (baseline/control)."""
    
    def __init__(self, simulator_url: str = "http://localhost:5000", 
                 interval: int = 3):
        """
        Initialize control baseline monitor.
        
        Args:
            simulator_url: URL of CityFlow simulator
            interval: Monitoring interval in seconds
        """
        self.simulator_url = simulator_url
        self.interval = interval
        self.data = []
        
    def get_average_travel_time(self) -> float:
        """
        Query simulator for current average travel time.
        
        Returns:
            Average travel time in seconds, or None if failed
        """
        try:
            response = requests.get(
                f"{self.simulator_url}/api/v1/snapshots/latest",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            avg_travel_time = data.get('average_travel_time')
            if avg_travel_time is not None:
                return float(avg_travel_time)
            else:
                logger.warning("No average_travel_time in response")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query simulator: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse response: {e}")
            return None
    
    def run(self, duration: float = float('inf')) -> None:
        """
        Run control baseline monitoring.
        
        Args:
            duration: Total duration to monitor in seconds (inf = forever)
        """
        logger.info(f"{'='*60}")
        logger.info("Control Baseline Monitor (No Adaptation)")
        logger.info(f"{'='*60}")
        logger.info(f"Simulator: {self.simulator_url}")
        logger.info(f"Interval: {self.interval} seconds")
        logger.info(f"Duration: {'Indefinite' if duration == float('inf') else f'{duration} seconds'}")
        logger.info(f"{'='*60}\n")
        
        start_time = time.time()
        cycle = 0
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Check if duration exceeded
                if elapsed >= duration:
                    logger.info(f"Duration of {duration}s reached. Stopping.")
                    break
                
                cycle += 1
                cycle_start = time.time()
                
                # Get average travel time from simulator
                avg_travel_time = self.get_average_travel_time()
                
                if avg_travel_time is not None:
                    # Store data point
                    data_point = {
                        'cycle': cycle,
                        'timestamp': time.time(),
                        'elapsed_time': elapsed,
                        'avg_travel_time': avg_travel_time
                    }
                    self.data.append(data_point)
                    
                    logger.info(f"Cycle {cycle:4d} | Elapsed: {elapsed:7.1f}s | "
                               f"Avg Travel Time: {avg_travel_time:7.2f}s")
                else:
                    logger.warning(f"Cycle {cycle:4d} | Failed to retrieve data")
                
                # Sleep for remainder of interval
                cycle_elapsed = time.time() - cycle_start
                sleep_time = max(0, self.interval - cycle_elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("\nMonitoring interrupted by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {e}", exc_info=True)
        finally:
            logger.info(f"\nMonitoring completed: {cycle} cycles, {len(self.data)} data points")
    
    def save_data(self, output_file: str) -> None:
        """
        Save collected data to CSV file.
        
        Args:
            output_file: Path to output CSV file
        """
        if not self.data:
            logger.warning("No data to save")
            return
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'cycle', 'timestamp', 'elapsed_time', 'avg_travel_time'
            ])
            writer.writeheader()
            writer.writerows(self.data)
        
        logger.info(f"Data saved to {output_path} ({len(self.data)} rows)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Control Baseline Monitor - No Adaptation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor for 5 minutes
  python control_baseline.py --duration 300 --output data/baseline.csv
  
  # Monitor indefinitely
  python control_baseline.py --output data/baseline.csv
  
  # Custom interval
  python control_baseline.py --interval 10 --duration 600 --output data/baseline_10s.csv
        """
    )
    
    parser.add_argument(
        '--simulator-url',
        default='http://localhost:5000',
        help='URL of CityFlow simulator (default: http://localhost:5000)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=3,
        help='Monitoring interval in seconds (default: 3)'
    )
    
    parser.add_argument(
        '--duration',
        type=float,
        default=float('inf'),
        help='Total duration to monitor in seconds (default: infinite)'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Output CSV file path'
    )
    
    args = parser.parse_args()
    
    # Create and run monitor
    monitor = ControlBaseline(
        simulator_url=args.simulator_url,
        interval=args.interval
    )
    
    monitor.run(duration=args.duration)
    monitor.save_data(args.output)
    
    logger.info("Control baseline monitoring complete")


if __name__ == '__main__':
    main()
