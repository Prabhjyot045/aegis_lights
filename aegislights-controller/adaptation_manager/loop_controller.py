"""MAPE-K loop orchestration controller."""

import time
import logging
from typing import Optional

from .monitor import Monitor
from .analyze import Analyzer
from .plan import Planner
from .execute import Executor
from .knowledge import KnowledgeBase
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig
from graph_manager.graph_model import TrafficGraph
from graph_manager.graph_visualizer import GraphVisualizer

logger = logging.getLogger(__name__)


class MAPELoopController:
    """Orchestrates the MAPE-K control loop."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 visualizer: GraphVisualizer, mape_config: MAPEConfig,
                 sim_config: SimulatorConfig):
        """
        Initialize MAPE loop controller.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            visualizer: Graph visualizer
            mape_config: MAPE configuration
            sim_config: Simulator configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.visualizer = visualizer
        self.config = mape_config
        
        # Initialize MAPE components
        self.monitor = Monitor(knowledge, graph, sim_config, mape_config)
        self.analyzer = Analyzer(knowledge, graph, mape_config)
        self.planner = Planner(knowledge, graph, mape_config)
        self.executor = Executor(knowledge, graph, sim_config, mape_config)
        
        self.current_cycle = 0
        self.running = False
        
    def run(self, duration: int) -> None:
        """
        Run the MAPE-K control loop for specified duration.
        
        Args:
            duration: Experiment duration in seconds
        """
        logger.info(f"Starting MAPE-K loop for {duration} seconds")
        logger.info(f"Cycle period: {self.config.cycle_period_seconds} seconds")
        
        self.running = True
        start_time = time.time()
        
        try:
            while self.running and (time.time() - start_time) < duration:
                cycle_start = time.time()
                self.current_cycle += 1
                
                logger.info(f"\n{'='*60}")
                logger.info(f"MAPE Cycle {self.current_cycle}")
                logger.info(f"{'='*60}")
                
                # Execute MAPE stages
                self._execute_mape_cycle()
                
                # Update visualizer
                self.visualizer.update(self.graph)
                
                # Wait for next cycle
                cycle_elapsed = time.time() - cycle_start
                sleep_time = max(0, self.config.cycle_period_seconds - cycle_elapsed)
                
                if sleep_time > 0:
                    logger.debug(f"Cycle completed in {cycle_elapsed:.2f}s, sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Cycle took {cycle_elapsed:.2f}s, longer than period {self.config.cycle_period_seconds}s")
                
        except KeyboardInterrupt:
            logger.info("MAPE loop interrupted by user")
            self.running = False
        except Exception as e:
            logger.error(f"Error in MAPE loop: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"MAPE loop completed {self.current_cycle} cycles")
    
    def _execute_mape_cycle(self) -> None:
        """Execute one complete MAPE-K cycle."""
        
        # MONITOR: Collect data from simulator
        logger.info("Stage: MONITOR")
        monitor_data = self.monitor.execute(self.current_cycle)
        logger.info(f"Monitored {len(monitor_data.get('edges', []))} edges")
        
        # ANALYZE: Identify problems and opportunities
        logger.info("Stage: ANALYZE")
        analysis_result = self.analyzer.execute(self.current_cycle, monitor_data)
        logger.info(f"Identified {len(analysis_result.get('hotspots', []))} hotspots")
        
        # PLAN: Generate adaptation strategy
        logger.info("Stage: PLAN")
        plan = self.planner.execute(self.current_cycle, analysis_result)
        logger.info(f"Planned adaptations for {len(plan.get('adaptations', []))} intersections")
        
        # EXECUTE: Apply adaptations safely
        logger.info("Stage: EXECUTE")
        execution_result = self.executor.execute(self.current_cycle, plan)
        
        if execution_result.get('rolled_back'):
            logger.warning("Performance degradation detected - ROLLBACK executed")
        elif execution_result.get('applied'):
            logger.info(f"Successfully applied {len(execution_result.get('applied', []))} adaptations")
        else:
            logger.info("No adaptations needed this cycle")
    
    def stop(self) -> None:
        """Stop the MAPE loop."""
        logger.info("Stopping MAPE loop...")
        self.running = False
