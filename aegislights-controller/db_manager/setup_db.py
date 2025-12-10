"""
Standalone script to setup and verify AegisLights database.
Run this script to initialize or reset the database.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_manager import initialize_database, verify_database
from db_manager.phase_library import PhaseLibrary
from config.experiment import ExperimentConfig


def main():
    """Setup and verify the database."""
    print("=" * 80)
    print("AegisLights Database Setup")
    print("=" * 80)
    
    # Get database path from config
    config = ExperimentConfig()
    db_path = config.db_path
    
    print(f"\nDatabase location: {db_path}")
    print(f"Creating database directory if needed...")
    
    # Initialize database
    try:
        db_path_absolute = initialize_database(db_path)
        print(f"✓ Database initialized successfully")
        print(f"  Path: {db_path_absolute}")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        return 1
    
    # Verify database
    print(f"\nVerifying database structure...")
    try:
        verification = verify_database(db_path)
        
        if verification['valid']:
            print(f"✓ Database verification passed")
            print(f"\nTables created:")
            for table in verification['tables']:
                print(f"  - {table}")
            
            print(f"\nIndices created:")
            for index in verification['indices']:
                print(f"  - {index}")
        else:
            print(f"✗ Database verification failed")
            print(f"  Missing tables: {verification.get('missing_tables', [])}")
            return 1
            
    except Exception as e:
        print(f"✗ Error verifying database: {e}")
        return 1
    
    # Initialize phase library
    print(f"\n" + "=" * 80)
    print("Phase Library Initialization")
    print("=" * 80)
    
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
            print(f"  Intersection {intersection_id}: {len(plans)} plans")
        
    except Exception as e:
        print(f"✗ Error loading default plans: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n" + "=" * 80)
    print(f"✓ Database is ready for use! 🎉")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
