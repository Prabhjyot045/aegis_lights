"""Execute stage: Apply signal changes safely with rollback capability."""

import time
import logging
from typing import Dict, List, Any

from .knowledge import KnowledgeBase
from .safety_validator import SafetyValidator
from .rollback_manager import RollbackManager
from .metrics import MetricsCalculator
from graph_manager.graph_model import TrafficGraph
from api.endpoints import SimulatorAPI
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig

logger = logging.getLogger(__name__)


class Executor:
    """Execute stage of MAPE-K loop."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 sim_config: SimulatorConfig, mape_config: MAPEConfig):
        """
        Initialize Executor.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            sim_config: Simulator configuration
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.api = SimulatorAPI(sim_config)
        self.config = mape_config
        
        # Initialize sub-components
        self.safety_validator = SafetyValidator(knowledge, mape_config)
        self.rollback_manager = RollbackManager(knowledge, mape_config)
        self.metrics = MetricsCalculator(knowledge, graph)
        
    def execute(self, cycle: int, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute plan: validate, apply, monitor performance, rollback if needed.
        
        Args:
            cycle: Current cycle number
            plan: Plan from Planner stage
            
        Returns:
            Dict containing execution results
        """
        timestamp = time.time()
        adaptations = plan.get('adaptations', [])
        
        if not adaptations:
            return {'cycle': cycle, 'applied': [], 'rolled_back': False}
        
        # Validate all adaptations before applying
        validated = self._validate_adaptations(adaptations)
        
        if not validated:
            logger.warning("Validation failed, skipping adaptations")
            return {'cycle': cycle, 'applied': [], 'rolled_back': False}
        
        # Apply adaptations at cycle boundary
        applied = self._apply_adaptations(adaptations, cycle, timestamp)
        
        # Calculate performance metrics
        metrics = self.metrics.calculate(cycle, timestamp)
        
        # Check for performance degradation
        should_rollback = self.rollback_manager.check_for_degradation(
            cycle, metrics
        )
        
        if should_rollback and self.config.enable_rollback:
            logger.warning("Performance degraded, initiating rollback")
            rolled_back = self._execute_rollback(cycle)
            return {
                'cycle': cycle,
                'applied': applied,
                'rolled_back': True,
                'metrics': metrics
            }
        
        # Update last-known-good configuration
        self.knowledge.update_last_known_good(cycle, adaptations)
        
        # Log execution
        self._log_execution(cycle, applied, metrics)
        
        return {
            'cycle': cycle,
            'applied': applied,
            'rolled_back': False,
            'metrics': metrics
        }
    
    def _validate_adaptations(self, adaptations: List[Dict]) -> bool:
        """Validate all adaptations meet safety constraints."""
        for adaptation in adaptations:
            intersection_id = adaptation['intersection_id']
            plan_id = adaptation['plan_id']
            
            # Validate plan exists and is safe
            if not self.safety_validator.validate_plan(intersection_id, plan_id):
                logger.warning(f"Plan {plan_id} failed safety validation for {intersection_id}")
                return False
            
            # Validate offset is reasonable
            offset = adaptation.get('offset', 0.0)
            if offset < 0 or offset > 300:  # Max 5 minutes offset
                logger.warning(f"Invalid offset {offset} for {intersection_id}")
                return False
        
        logger.debug(f"All {len(adaptations)} adaptations validated successfully")
        return True
    
    def _apply_adaptations(self, adaptations: List[Dict], cycle: int,
                          timestamp: float) -> List[Dict]:
        """Apply validated adaptations to simulator."""
        logger.debug(f"Applying {len(adaptations)} adaptations at cycle {cycle}")
        applied = []
        
        for adaptation in adaptations:
            intersection_id = adaptation['intersection_id']
            plan_id = adaptation['plan_id']
            offset = adaptation.get('offset', 0.0)
            
            try:
                # Update signal timing via API
                success = self.api.update_signal_timing(
                    intersection_id=intersection_id,
                    plan_id=plan_id,
                    offset=offset
                )
                
                if success:
                    # Update graph model with new plan
                    node = self.graph.nodes.get(intersection_id)
                    if node:
                        node.current_plan_id = plan_id
                        node.offset = offset
                    
                    applied.append({
                        'intersection_id': intersection_id,
                        'plan_id': plan_id,
                        'offset': offset,
                        'cycle': cycle,
                        'timestamp': timestamp
                    })
                    logger.debug(f"Applied {plan_id} to {intersection_id}")
                else:
                    logger.warning(f"Failed to apply {plan_id} to {intersection_id}")
                    
            except Exception as e:
                logger.error(f"Error applying adaptation to {intersection_id}: {e}")
        
        return applied
    
    def _execute_rollback(self, cycle: int) -> bool:
        """Rollback to last-known-good configuration."""
        logger.info("Executing rollback to last-known-good configuration")
        
        try:
            # Get last-known-good configuration for all intersections
            lkg_configs = []
            timestamp = time.time()
            
            for intersection_id in self.graph.nodes.keys():
                lkg = self.knowledge.get_last_known_good(intersection_id)
                if lkg:
                    lkg_configs.append(lkg['config'])
            
            if not lkg_configs:
                logger.error("No last-known-good configuration available")
                return False
            
            # Apply last-known-good plans
            for adaptation in lkg_configs:
                intersection_id = adaptation['intersection_id']
                plan_id = adaptation['plan_id']
                offset = adaptation.get('offset', 0.0)
                
                self.api.update_signal_timing(
                    intersection_id=intersection_id,
                    plan_id=plan_id,
                    offset=offset
                )
                
                # Update graph model
                node = self.graph.nodes.get(intersection_id)
                if node:
                    node.current_plan_id = plan_id
                    node.offset = offset
            
            # Log rollback event
            self.knowledge.log_rollback(cycle, timestamp, lkg_configs)
            logger.info(f"Rollback successful: restored {len(lkg_configs)} signal plans")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def _log_execution(self, cycle: int, applied: List, metrics: Dict) -> None:
        """Log execution for explainability."""
        logger.debug(f"Logging execution for cycle {cycle}")
        
        # Store execution record in knowledge base
        execution_record = {
            'cycle': cycle,
            'timestamp': time.time(),
            'applied_count': len(applied),
            'adaptations': applied,
            'metrics': metrics
        }
        
        self.knowledge.log_execution(cycle, execution_record)
        
        # Log summary
        if applied:
            logger.info(f"Cycle {cycle} execution summary:")
            logger.info(f"  Applied adaptations: {len(applied)}")
            logger.info(f"  Avg delay: {metrics.get('avg_delay', 0):.2f}s")
            logger.info(f"  Avg queue: {metrics.get('avg_queue', 0):.2f} vehicles")
            logger.info(f"  Network cost: {metrics.get('network_cost', 0):.2f}")
