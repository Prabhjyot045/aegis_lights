"""MAPE-K loop orchestration controller."""

import time
import logging
from typing import Optional, Dict

from .monitor import Monitor
from .analyze import Analyzer
from .plan import Planner
from .execute import Executor
from .metrics import MetricsCalculator
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
        self.metrics_calc = MetricsCalculator(knowledge, graph)
        
        self.current_cycle = 0
        self.running = False
        
        # Track adaptations for reward calculation
        self.last_adaptations = []
        self.last_cycle_cost = None
        
    def run(self, duration: float = float('inf')) -> None:
        """
        Run the MAPE-K control loop for specified duration.
        
        Controller runs continuously, adapting every cycle_period_seconds,
        until one of the following occurs:
        - Maximum duration reached (if specified)
        - Simulator stops responding (connection loss)
        - User interrupts with Ctrl+C
        
        Args:
            duration: Maximum duration in seconds (default: inf = run indefinitely)
        """
        if duration == float('inf'):
            logger.info("Starting MAPE-K loop (indefinite duration)")
        else:
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
                
                # Update visualizer (non-blocking, thread-safe)
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
            # Stop visualizer
            self.visualizer.stop()
    
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
        
        # CALCULATE METRICS: Compute and store performance metrics (pass monitor data for avg_travel_time)
        metrics = self.metrics_calc.calculate(self.current_cycle, time.time(), monitor_data)
        logger.debug(f"Metrics calculated: avg_delay={metrics.get('avg_delay', 0):.2f}s, "
                    f"avg_trip_time={metrics.get('avg_trip_time', 0):.2f}s, "
                    f"network_cost={metrics.get('network_cost', 0):.2f}")
        
        # UPDATE BANDIT: Calculate rewards and update bandit statistics
        self._update_bandit_rewards(plan.get('adaptations', []), metrics, analysis_result)
        
        # UPDATE VISUALIZER: Update metrics for display
        self.visualizer.update_metrics(
            cycle=self.current_cycle,
            incidents=len(analysis_result.get('incidents', [])),
            adaptations=len(plan.get('adaptations', [])),
            avg_delay=metrics.get('avg_delay', 0.0)
        )
    
    def _update_bandit_rewards(self, adaptations: list, metrics: Dict, analysis_result: Dict) -> None:
        """
        Update bandit with rewards based on performance metrics.
        
        Reward is calculated as negative network cost (lower cost = higher reward).
        Additional penalties for spillbacks and incidents.
        
        Args:
            adaptations: List of applied adaptations
            metrics: Performance metrics for this cycle
            analysis_result: Analysis results with context
        """
        if not adaptations:
            return
        
        # Calculate reward: negative network cost (we want to minimize cost)
        network_cost = metrics.get('network_cost', 0.0)
        reward = -network_cost
        
        # Apply penalties
        spillback_penalty = metrics.get('total_spillbacks', 0) * 10.0
        reward -= spillback_penalty
        
        # Update bandit for each adaptation
        for adaptation in adaptations:
            intersection_id = adaptation.get('intersection_id')
            plan_id = adaptation.get('plan_id')
            
            if not intersection_id or not plan_id:
                continue
            
            # Build context for this intersection
            context = self._build_adaptation_context(intersection_id, analysis_result)
            
            # Update bandit with observed reward
            try:
                self.planner.bandit.update_reward(
                    intersection_id=intersection_id,
                    plan_id=plan_id,
                    context=context,
                    reward=reward
                )
                logger.debug(f"Updated bandit for {intersection_id}/{plan_id}: reward={reward:.2f}")
            except Exception as e:
                logger.error(f"Failed to update bandit for {intersection_id}/{plan_id}: {e}")
    
    def _build_adaptation_context(self, intersection_id: str, analysis_result: Dict) -> Dict:
        """
        Build context dict for bandit update.
        
        Args:
            intersection_id: Intersection ID
            analysis_result: Analysis results
            
        Returns:
            Context dict with features
        """
        context = {
            'intersection_id': intersection_id,
            'cycle': self.current_cycle,
            'avg_cost': analysis_result.get('avg_cost', 0.0)
        }
        
        # Add features from graph
        node = self.graph.nodes.get(intersection_id)
        if node:
            # Calculate avg queue/delay from outgoing edges
            queues = []
            delays = []
            for edge_key in node.outgoing_edges:
                edge = self.graph.get_edge(edge_key[0], edge_key[1])
                if edge:
                    queues.append(edge.current_queue)
                    delays.append(edge.current_delay)
            
            if queues:
                context['avg_queue'] = sum(queues) / len(queues)
            if delays:
                context['avg_delay'] = sum(delays) / len(delays)
        
        return context
    
    def stop(self) -> None:
        """Stop the MAPE loop."""
        logger.info("Stopping MAPE loop...")
        self.running = False
