#!/usr/bin/env python3
"""
run_net.py - Run and test CityFlow network simulation
Place this file in the same folder as config.json, flow.json, and roadnet.json
"""

import cityflow
import json
import os
import time

def run_simulation():
    """Run the simulation and test basic functionality"""
    
    # Check if required files exist
    required_files = ['config.json', 'roadnet.json', 'flow.json']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print("Error! Missing files: {}".format(missing_files))
        print("Please ensure config.json, roadnet.json, and flow.json are in the same directory")
        return False
    
    print("All required files found")
    
    # Validate JSON files
    for file in required_files:
        try:
            with open(file, 'r') as f:
                json.load(f)
            print("{} is valid JSON".format(file))
        except json.JSONDecodeError as e:
            print("{} has invalid JSON: {}".format(file, e))
            return False
    
    try:
        # Initialize engine
        print("Initializing CityFlow engine...")
        eng = cityflow.Engine(config_file='/Users/yixing/Desktop/ece750/aegis_lights/CityFlow/aegis_lights_simulator/config.json', thread_num=1)
        print("Engine created successfully!")
        
        # Get simulation parameters from config
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        interval = config.get('interval', 1.0)
        total_steps = 10  # Run for 1 hour of simulation time
        
        print("\nStarting simulation:")
        print("   - Time interval: {} seconds per step".format(interval))
        print("   - Total steps: {}".format(total_steps))
        print("   - Total simulation time: {} seconds".format(total_steps * interval))
        
        # Main simulation loop
        print("\nRunning simulation...")
        start_time = time.time()
        
        for step in range(total_steps):
            eng.next_step()
            
            # Print progress every 100 steps
            if step % 2 == 0:
                current_time = eng.get_current_time()
                vehicle_count = eng.get_vehicle_count()
                total_vehicles = len(eng.get_vehicles(include_waiting=True))
                
                print("   Step {:4d} | Time: {:6.1f}s | Running vehicles: {:3d} | Total vehicles: {:3d}".format(
                    step, current_time, vehicle_count, total_vehicles))

            if step % 5 == 0:  # Test API every 500 steps
                running_count = len(eng.get_vehicles())
                total_count = len(eng.get_vehicles(include_waiting=True))
                
                # Verify basic invariants
                assert running_count <= total_count, "Running vehicles should be <= total vehicles"
                assert running_count == eng.get_vehicle_count(), "Vehicle count mismatch"
                
                # Test data retrieval (these should not crash)
                lane_vehicle_count = eng.get_lane_vehicle_count()
                lane_waiting_count = eng.get_lane_waiting_vehicle_count()
                lane_vehicles = eng.get_lane_vehicles()
                vehicle_speed = eng.get_vehicle_speed()
                vehicle_distance = eng.get_vehicle_distance()
                
                if step == 0:
                    print(" All API functions working correctly")
        
        end_time = time.time()
        real_time_elapsed = end_time - start_time
        simulation_time_elapsed = total_steps * interval
        
        print("\nSimulation completed!")
        print("   Real time elapsed: {:.2f} seconds".format(real_time_elapsed))
        print("   Simulation time: {:.2f} seconds".format(simulation_time_elapsed))
        print("   Speed ratio: {:.2f}x".format(simulation_time_elapsed/real_time_elapsed))
        
        # Final statistics
        final_vehicles = eng.get_vehicles()
        print("   Final running vehicles: {}".format(len(final_vehicles)))
        
        # Test replay file change (like test_api.py)
        print("\n Testing replay file change...")
        eng.set_replay_file("replay_final.txt")
        eng.next_step()  # Take one more step with new replay file
        print("Replay file changed successfully")
        
        # Clean up
        del eng
        print(" Engine cleanup completed")
        
        return True
        
    except Exception as e:
        print("Error during simulation: {}".format(e))
        return False

def test_specific_scenario():
    """Test specific aspects of your 5-intersection network"""
    print("\n" + "="*50)
    print("Testing 5-Intersection Network Specifics")
    print("="*50)
    
    try:
        eng = cityflow.Engine(config_file='config.json', thread_num=1)
        
        # Run a shorter test
        test_steps = 100
        
        for step in range(test_steps):
            eng.next_step()
            
            if step % 20 == 0:
                # Check intersection-specific data
                lane_vehicles = eng.get_lane_vehicles()
                vehicle_speeds = eng.get_vehicle_speed()
                
                # Count vehicles in different parts of the network
                total_vehicles = len(eng.get_vehicles())
                avg_speed = sum(vehicle_speeds.values())/max(1, len(vehicle_speeds))
                
                print("   Step {:3d} | Vehicles: {:2d} | Avg speed: {:.1f} m/s".format(
                    step, total_vehicles, avg_speed))
        
        print(" 5-intersection network test completed")
        del eng
        
    except Exception as e:
        print("Scenario test failed: {}".format(e))

if __name__ == '__main__':
    print("CityFlow Network Runner")
    print("=" * 40)
    
    # Run main simulation
    success = run_simulation()
    
    if success:
        # Run additional tests
        test_specific_scenario()
        
        print("\n All tests completed successfully!")
        print("\n Generated files:")
        generated_files = ['replay.txt', 'replay_final.txt', 'roadnetlog.json']
        for file in generated_files:
            if os.path.exists(file):
                print("   {} (found)".format(file))
            else:
                print("   {} (not found)".format(file))
    else:
        print("\n Simulation failed. Please check the error messages above.")
        exit(1)