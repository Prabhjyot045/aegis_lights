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
        """
        Validate all adaptations meet safety constraints.
        
        Checks:
        - Valid intersection IDs (signalized only)
        - Valid phase_id (0-3 for CityFlow)
        - Valid offsets (non-negative)
        - Plan exists in phase library
        
        Args:
            adaptations: List of adaptation dicts
            
        Returns:
            True if all valid, False otherwise
        """
        signalized_intersections = {'A', 'B', 'C', 'D', 'E'}
        
        for adaptation in adaptations:
            intersection_id = adaptation.get('intersection_id')
            plan_id = adaptation.get('plan_id')
            phase_id = adaptation.get('phase_id', 0)
            offset = adaptation.get('offset', 0.0)
            
            # Validate intersection is signalized
            if intersection_id not in signalized_intersections:
                logger.warning(f"Invalid intersection {intersection_id} (not signalized)")
                return False
            
            # Validate phase_id is in valid range for CityFlow
            if not isinstance(phase_id, int) or phase_id < 0 or phase_id > 3:
                logger.warning(f"Invalid phase_id {phase_id} for {intersection_id} (must be 0-3)")
                return False
            
            # Validate plan exists and is safe
            if not self.safety_validator.validate_plan(intersection_id, plan_id):
                logger.warning(f"Plan {plan_id} failed safety validation for {intersection_id}")
                return False
            
            # Validate offset is reasonable
            if offset < 0 or offset > 300:  # Max 5 minutes offset
                logger.warning(f"Invalid offset {offset} for {intersection_id}")
                return False
        
        logger.debug(f"All {len(adaptations)} adaptations validated successfully")
        return True
    
    def _apply_adaptations(self, adaptations: List[Dict], cycle: int,
                          timestamp: float) -> List[Dict]:
        """
        Apply validated adaptations to simulator.
        
        For CityFlow: Sends phase_id (0-3) to each intersection.
        Also stores configuration in database for tracking.
        
        Args:
            adaptations: List of adaptation dicts with phase_id
            cycle: Current cycle number
            timestamp: Current timestamp
            
        Returns:
            List of successfully applied adaptations
        """
        logger.info(f"[Execute] Applying {len(adaptations)} adaptations at cycle {cycle}")
        applied = []
        
        for adaptation in adaptations:
            intersection_id = adaptation['intersection_id']
            plan_id = adaptation['plan_id']
            phase_id = adaptation.get('phase_id', 0)  # CityFlow phase index
            offset = adaptation.get('offset', 0.0)
            cycle_length = adaptation.get('cycle_length', 80)
            is_incident_mode = adaptation.get('is_incident_mode', False)
            
            try:
                # Update signal timing via API (sends phase_id to CityFlow)
                success = self.api.update_signal_timing(
                    intersection_id=intersection_id,
                    phase_id=phase_id,
                    plan_id=plan_id
                )
                
                if success:
                    # Update graph model with new plan
                    node = self.graph.nodes.get(intersection_id)
                    if node:
                        node.current_plan_id = plan_id
                        node.offset = offset
                        node.cycle_length = cycle_length
                    
                    # Store configuration in database
                    self.knowledge.store_signal_config(
                        intersection_id=intersection_id,
                        cycle=cycle,
                        timestamp=timestamp,
                        plan_id=plan_id,
                        phase_id=phase_id,
                        cycle_length=cycle_length,
                        offset=offset,
                        is_incident_mode=is_incident_mode
                    )
                    
                    applied.append({
                        'intersection_id': intersection_id,
                        'plan_id': plan_id,
                        'phase_id': phase_id,
                        'offset': offset,
                        'cycle': cycle,
                        'timestamp': timestamp,
                        'is_incident_mode': is_incident_mode
                    })
                    
                    logger.info(f"Applied phase {phase_id} (plan {plan_id}) to {intersection_id}")
                else:
                    logger.warning(f"Failed to apply phase {phase_id} to {intersection_id}")
                    
            except Exception as e:
                logger.error(f"Error applying adaptation to {intersection_id}: {e}", exc_info=True)
        
        logger.info(f"[Execute] Successfully applied {len(applied)}/{len(adaptations)} adaptations")
        return applied
    
    def _execute_rollback(self, cycle: int) -> bool:
        """
        Rollback to last-known-good configuration.
        
        Restores previous signal phases that were performing well.
        
        Args:
            cycle: Current cycle number
            
        Returns:
            True if rollback successful, False otherwise
        """
        logger.warning("[Execute] Executing rollback to last-known-good configuration")
        
        try:
            # Get last-known-good configuration for all signalized intersections
            lkg_configs = []
            timestamp = time.time()
            signalized_intersections = {'A', 'B', 'C', 'D', 'E'}
            
            for intersection_id in signalized_intersections:
                if intersection_id in self.graph.nodes:
                    lkg = self.knowledge.get_last_known_good(intersection_id)
                    if lkg:
                        lkg_configs.append(lkg['config'])
            
            if not lkg_configs:
                logger.error("No last-known-good configuration available for rollback")
                return False
            
            # Apply last-known-good plans
            rolled_back = 0
            for adaptation in lkg_configs:
                intersection_id = adaptation['intersection_id']
                plan_id = adaptation['plan_id']
                phase_id = adaptation.get('phase_id', 0)
                offset = adaptation.get('offset', 0.0)
                
                success = self.api.update_signal_timing(
                    intersection_id=intersection_id,
                    phase_id=phase_id,
                    plan_id=plan_id
                )
                
                if success:
                    # Update graph model
                    node = self.graph.nodes.get(intersection_id)
                    if node:
                        node.current_plan_id = plan_id
                        node.offset = offset
                    rolled_back += 1
            
            # Log rollback event
            self.knowledge.log_rollback(cycle, timestamp, lkg_configs)
            logger.warning(f"[Execute] Rollback successful: restored {rolled_back} signal plans")
            return rolled_back > 0
            
        except Exception as e:
            logger.error(f"[Execute] Rollback failed: {e}", exc_info=True)
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
