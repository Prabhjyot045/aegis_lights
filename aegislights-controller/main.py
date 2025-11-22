"""
AegisLights - Self-Adaptive Traffic Signal Control System
Main orchestrator for initialization, MAPE loop execution, and cleanup.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from db_manager import verify_database, cleanup_database, export_experiment_data
from config.experiment import ExperimentConfig
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig
from adaptation_manager.knowledge import KnowledgeBase
from adaptation_manager.loop_controller import MAPELoopController
from graph_manager.graph_model import TrafficGraph
from graph_manager.graph_visualizer import GraphVisualizer
from utils.logging import setup_logging


def main():
    """Main entry point for AegisLights controller."""
    
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("AegisLights Self-Adaptive Traffic Signal Control System")
    logger.info("=" * 80)
    
    try:
        # Load configurations
        logger.info("Loading configurations...")
        exp_config = ExperimentConfig()
        mape_config = MAPEConfig()
        sim_config = SimulatorConfig()
        
        # Verify database exists and is valid
        logger.info("Verifying database...")
        db_path = exp_config.db_path
        verification = verify_database(db_path)
        
        if not verification['valid']:
            logger.error(f"Database validation failed!")
            logger.error(f"Missing tables: {verification.get('missing_tables', [])}")
            logger.error(f"Please run 'python setup_db.py' first to initialize the database")
            return 1
        
        logger.info(f"Database verified successfully: {db_path}")
        
        # Initialize graph model
        logger.info("Initializing traffic graph model...")
        graph = TrafficGraph()
        
        # Initialize knowledge base
        logger.info("Initializing knowledge base...")
        knowledge = KnowledgeBase(db_path, graph)
        
        # Initialize visualizer
        logger.info("Starting graph visualizer...")
        visualizer = GraphVisualizer(
            graph=graph,
            record=exp_config.record_visualization,
            output_dir=exp_config.output_dir
        )
        visualizer.start()
        
        # Initialize and run MAPE loop
        logger.info("Starting MAPE-K control loop...")
        loop_controller = MAPELoopController(
            knowledge=knowledge,
            graph=graph,
            visualizer=visualizer,
            mape_config=mape_config,
            sim_config=sim_config
        )
        
        # Run the adaptation loop
        loop_controller.run(duration=exp_config.duration_seconds)
        
        logger.info("MAPE-K control loop completed successfully")
        
    except KeyboardInterrupt:
        logger.warning("Experiment interrupted by user")
    except Exception as e:
        logger.error(f"Error during experiment execution: {e}", exc_info=True)
        return 1
    finally:
        # Export experiment data
        logger.info("Exporting experiment data...")
        try:
            export_experiment_data(
                db_path=db_path,
                output_dir=exp_config.output_dir,
                experiment_name=exp_config.name
            )
            logger.info(f"Data exported to: {exp_config.output_dir}")
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
        
        # Stop visualizer
        if 'visualizer' in locals():
            logger.info("Stopping visualizer...")
            visualizer.stop()
        
        # Cleanup database
        if exp_config.cleanup_on_exit:
            logger.info("Cleaning up database...")
            cleanup_database(db_path)
            logger.info("Database cleaned up")
        
        logger.info("=" * 80)
        logger.info("AegisLights shutdown complete")
        logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
