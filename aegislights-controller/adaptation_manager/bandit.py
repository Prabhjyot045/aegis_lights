"""Contextual bandit algorithm for plan selection."""

import logging
import math
import random
from typing import Dict, List

from .knowledge import KnowledgeBase
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class ContextualBandit:
    """Contextual bandit for adaptive plan selection."""
    
    def __init__(self, knowledge: KnowledgeBase, mape_config: MAPEConfig):
        """
        Initialize contextual bandit.
        
        Args:
            knowledge: Knowledge base interface
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.config = mape_config
        self.algorithm = mape_config.bandit_algorithm
        
    def select_plan(self, intersection_id: str, context: Dict, 
                   valid_plans: List[Dict]) -> Dict:
        """
        Select a signal plan using contextual bandit algorithm.
        
        Args:
            intersection_id: Intersection identifier
            context: Context features (queue lengths, delays, etc.)
            valid_plans: List of valid plans from phase library
            
        Returns:
            Selected plan dict
        """
        if self.algorithm == "ucb":
            return self._select_ucb(intersection_id, context, valid_plans)
        elif self.algorithm == "thompson_sampling":
            return self._select_thompson_sampling(intersection_id, context, valid_plans)
        else:
            # Fallback to random
            return random.choice(valid_plans)
    
    def update_reward(self, intersection_id: str, plan_id: str, 
                     context: Dict, reward: float) -> None:
        """
        Update bandit state with observed reward.
        
        Args:
            intersection_id: Intersection identifier
            plan_id: Selected plan identifier
            context: Context features used
            reward: Observed reward (negative delay + spillback penalty)
        """
        # Get current stats
        stats = self._get_arm_stats(intersection_id, plan_id, context)
        
        # Update statistics
        new_times_selected = stats['times_selected'] + 1
        new_total_reward = stats['total_reward'] + reward
        new_avg_reward = new_total_reward / new_times_selected
        
        # Store updated stats
        self._update_arm_stats(
            intersection_id, plan_id, context,
            new_times_selected, new_total_reward, new_avg_reward
        )
        
        logger.debug(f"Updated bandit: {intersection_id}/{plan_id}, reward={reward:.2f}, avg={new_avg_reward:.2f}")
    
    def _select_ucb(self, intersection_id: str, context: Dict,
                   valid_plans: List[Dict]) -> Dict:
        """Select plan using Upper Confidence Bound (UCB)."""
        # TODO: Implement UCB algorithm
        # UCB = avg_reward + exploration_factor * sqrt(log(total_pulls) / arm_pulls)
        
        best_plan = None
        best_ucb = float('-inf')
        
        for plan in valid_plans:
            # Get arm statistics
            stats = self._get_arm_stats(intersection_id, plan['plan_id'], context)
            
            if stats['times_selected'] == 0:
                # Always try untried arms first
                return plan
            
            # Calculate UCB
            avg_reward = stats['avg_reward']
            confidence = self.config.exploration_factor * math.sqrt(
                math.log(stats['total_pulls']) / stats['times_selected']
            )
            ucb = avg_reward + confidence
            
            if ucb > best_ucb:
                best_ucb = ucb
                best_plan = plan
        
        return best_plan if best_plan else valid_plans[0]
    
    def _select_thompson_sampling(self, intersection_id: str, context: Dict,
                                  valid_plans: List[Dict]) -> Dict:
        """
        Select plan using Thompson Sampling.
        
        Uses Beta distribution for reward sampling based on historical
        success/failure counts.
        
        Args:
            intersection_id: Intersection ID
            context: Context features
            valid_plans: List of valid plans
            
        Returns:
            Selected plan
        """
        import numpy as np
        
        best_plan = None
        best_sample = float('-inf')
        
        for plan in valid_plans:
            stats = self._get_arm_stats(intersection_id, plan['plan_id'], context)
            
            if stats['times_selected'] == 0:
                # Always try untried arms first
                return plan
            
            # Model rewards as Beta distribution
            # Convert avg_reward to success probability (normalize to [0,1])
            # Assuming rewards are in range [-100, 0], normalize to [0, 1]
            success_rate = max(0, min(1, (stats['avg_reward'] + 100) / 100))
            
            # Beta parameters: alpha = successes, beta = failures
            alpha = max(1, stats['times_selected'] * success_rate)
            beta = max(1, stats['times_selected'] * (1 - success_rate))
            
            # Sample from Beta distribution
            sample = np.random.beta(alpha, beta)
            
            if sample > best_sample:
                best_sample = sample
                best_plan = plan
        
        return best_plan if best_plan else valid_plans[0]
    
    def _get_arm_stats(self, intersection_id: str, plan_id: str,
                      context: Dict) -> Dict:
        """
        Get statistics for a bandit arm from knowledge base.
        
        Args:
            intersection_id: Intersection ID
            plan_id: Plan ID
            context: Context features (for context hash)
            
        Returns:
            Arm statistics dictionary
        """
        # Query bandit state from knowledge base
        stats = self.knowledge.get_bandit_stats(intersection_id, plan_id)
        
        if stats is None:
            # Initialize new arm
            return {
                'times_selected': 0,
                'total_reward': 0.0,
                'avg_reward': 0.0,
                'confidence': 1.0,
                'total_pulls': 1  # Total pulls across all arms (for UCB)
            }
        
        return stats
    
    def _update_arm_stats(self, intersection_id: str, plan_id: str,
                         context: Dict, times_selected: int,
                         total_reward: float, avg_reward: float) -> None:
        """
        Update bandit arm statistics in knowledge base.
        
        Args:
            intersection_id: Intersection ID
            plan_id: Plan ID  
            context: Context features
            times_selected: Number of times this arm was selected
            total_reward: Cumulative reward
            avg_reward: Average reward
        """
        self.knowledge.update_bandit_stats(
            intersection_id=intersection_id,
            plan_id=plan_id,
            times_selected=times_selected,
            total_reward=total_reward,
            avg_reward=avg_reward
        )
