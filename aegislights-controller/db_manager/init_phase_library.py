"""
Initialize phase library with default CityFlow signal timing plans.
Run this script after setting up the database to populate phase library.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_manager.phase_library import PhaseLibrary
from config.experiment import ExperimentConfig


def main():
    """Initialize phase library with default plans."""
    print("=" * 80)
    print("AegisLights Phase Library Initialization")
    print("=" * 80)
    
    # Get database path from config
    config = ExperimentConfig()
    db_path = config.db_path
    
    print(f"\nDatabase: {db_path}")
    
    # Initialize phase library
    try:
        phase_lib = PhaseLibrary(db_path)
        print(f"✓ Phase library initialized")
    except Exception as e:
        print(f"✗ Error initializing phase library: {e}")
        return 1
    
    # Load default plans for all signalized intersections
    print(f"\nLoading default signal timing plans...")
    try:
        phase_lib.load_default_plans()
        print(f"✓ Default plans loaded successfully")
        
        # Show what was loaded
        print(f"\nSignal timing plans created:")
        for intersection_id in PhaseLibrary.SIGNALIZED_INTERSECTIONS:
            plans = phase_lib.get_plans(intersection_id)
            print(f"\n  Intersection {intersection_id}: {len(plans)} plans")
            for plan in plans:
                print(f"    - {plan['plan_name']} (Phase {plan['phases'].get('phase_id', 'N/A')})")
        
        print(f"\n✓ Phase library ready for use! 🚦")
        return 0
        
    except Exception as e:
        print(f"✗ Error loading default plans: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
