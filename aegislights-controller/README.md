# AegisLights Traffic Control System

**Adaptive Traffic Signal Control using MAPE-K Self-Adaptation with CityFlow**

A research implementation of intelligent traffic signal control that uses runtime self-adaptation to minimize travel time and prevent network congestion. The controller continuously adapts signal timing based on real-time traffic conditions from the CityFlow simulator.

---

## 🎯 Overview

AegisLights implements a MAPE-K (Monitor-Analyze-Plan-Execute over shared Knowledge) control loop integrated with CityFlow simulator. The controller:

- **Monitors** real-time traffic from CityFlow (queue lengths, delays, incidents)
- **Analyzes** congestion patterns and identifies alternative routes  
- **Plans** signal timing adaptations using contextual multi-armed bandits
- **Executes** changes safely with validation and automatic rollback
- **Learns** from experience to improve future decisions

**Key Feature**: Controller runs **continuously** (indefinitely) adapting every N seconds until the CityFlow simulator stops responding or you press Ctrl+C. Network topology, traffic demand, and scenarios are all determined by CityFlow configuration, not by the controller.

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+ required
conda activate aegis_lights  # ALWAYS activate environment first

# CityFlow simulator must be running
# Check: curl http://localhost:5000/health
```

### Installation

```bash
cd aegislights-controller

# Create conda environment
conda create -n aegis_lights python=3.10
conda activate aegis_lights

# Install dependencies
pip install -r requirements.txt
pip install flask flask-cors  # For web visualizer
```

### Database Setup

```bash
conda activate aegis_lights
python db_manager/setup_db.py
```

Creates `data/aegis_lights.db` with 8 tables for logging and state management.

### Running the Controller

```bash
# IMPORTANT: Always activate conda environment first!
conda activate aegis_lights

# Start controller (runs indefinitely)
python main.py
```

The controller will:
1. Connect to CityFlow at `http://localhost:5000`
2. Start web visualizer at `http://localhost:5001` 
3. Begin MAPE-K control loop (60-second cycles by default)
4. Adapt signal phases every cycle based on traffic
5. Run until simulator stops or you press Ctrl+C

**View Live Visualization**: http://localhost:5001

---

## 📊 System Architecture

### MAPE-K Loop with CityFlow

```
┌────────────────────────────────────────────────┐
│      CityFlow Simulator (Port 5000)            │
│  - 5 Signalized Intersections (A-E)           │
│  - 8 Virtual Nodes (1-8)                      │
│  - 28 Directed Edges                          │
│  - 4-Phase Timing Control                     │
└──────┬──────────────────────────┬──────────────┘
       │ HTTP API                 │ Phase Commands
       │ /snapshots/latest        │ /intersections/{id}/plan
       ▼                          ▲
  ┌─────────┐              ┌──────────┐
  │ MONITOR │◄─────────────┤ Knowledge│
  └────┬────┘              │   Base   │
       │                   │ (SQLite) │
  ┌────▼────┐              └────▲─────┘
  │ ANALYZE │◄──────────────────┤
  └────┬────┘                   │
       │                        │
  ┌────▼────┐                   │
  │  PLAN   │◄──────────────────┤
  └────┬────┘                   │
       │                        │
  ┌────▼────┐                   │
  │ EXECUTE │───────────────────►
  └────┬────┘
       │
       ▼ Apply to CityFlow
```

### CityFlow Network Topology

```
      1           3
      ↓           ↓
  ┌───A───┐   ┌───B───┐
2→│  🚦  │──→│  🚦  │→4
  └───┬───┘   └───┬───┘
      │           │
  ┌───C───┐   ┌───D───┐
5→│  🚦  │←──│  🚦  │→7
  └───┬───┘   └───┬───┘
      │           │
  ┌───E───┐       8
6→│  🚦  │
  └───────┘

🚦 = Signalized (A-E)
1-8 = Virtual nodes
→ = Directed edges
```

- 5 signalized intersections with 4-phase control
- 8 virtual entry/exit points  
- 28 total directed edges
- Phase IDs: 0-3 per intersection

---

## ⚙️ Configuration

### MAPE Loop Settings (`config/mape.py`)

```python
@dataclass
class MAPEConfig:
    cycle_period_seconds: int = 60  # How often to adapt
    
    # Monitor
    rolling_window_size: int = 5  # Smoothing window
    
    # Analyze
    hotspot_threshold: float = 0.7  # 70th percentile
    k_shortest_paths: int = 3  # Alternative routes
    
    # Plan
    bandit_algorithm: str = "ucb"  # or "thompson_sampling"
    exploration_factor: float = 0.2
    
    # Execute
    enable_rollback: bool = True
    performance_degradation_threshold: float = 0.1  # 10%
```

### Simulator Connection (`config/simulator.py`)

```python
@dataclass
class SimulatorConfig:
    host: str = "localhost"
    port: int = 5000
    base_url: str = "http://localhost:5000"
    
    endpoint_get_network: str = "/api/v1/snapshots/latest"
    endpoint_set_signal: str = "/api/v1/intersections/{intersection_id}/plan"
    endpoint_health: str = "/health"
    
    timeout_seconds: int = 30
    retry_attempts: int = 3
```

### Runtime Settings (`config/experiment.py`)

```python
@dataclass
class ExperimentConfig:
    name: str = "aegis_experiment_001"
    
    # Duration: None = run indefinitely until simulator stops
    max_duration_seconds: int = None  # Or set to 3600 for 1 hour
    
    # Database path (auto-set if None)
    db_path: str = None  # Defaults to data/aegis_lights.db
    
    # Visualization
    enable_web_visualizer: bool = True  # Web-based (recommended)
    record_visualization: bool = False  # Matplotlib video
```

**Important**: Network topology, traffic demand, and incident scenarios are controlled by CityFlow's configuration files (`cityflow/net_config/`), not by the controller.

---

## 🔄 MAPE-K Components

### Monitor Stage
- **What**: Polls CityFlow API for traffic state
- **Input**: Lane-level data (AB_0, AB_1, ...)
- **Process**: Aggregates lanes → edges, detects anomalies
- **Output**: Updated graph with queues, delays, incidents
- **Frequency**: Every MAPE cycle (60s default)

### Analyze Stage  
- **What**: Identifies congestion patterns
- **Process**: 
  - Compute edge costs: `1.0·delay + 0.5·queue + 10·spillback + 20·incident`
  - Find hotspots (>70th percentile)
  - Find k=3 bypass routes
  - Predict trends (exponential smoothing)
- **Output**: Hotspots, bypasses, targets, coordination groups

### Plan Stage
- **What**: Selects optimal signal plans
- **Process**:
  - Build context [queue_ratio, delay, time, incident_flag]
  - Query phase library for valid plans
  - Use contextual bandit (UCB) to select
  - Calculate offsets for coordination
- **Output**: List of signal adaptations (phase IDs per intersection)

### Execute Stage
- **What**: Safely applies signal changes
- **Process**:
  - Validate safety (NEMA conflicts, clearance times)
  - POST phase to CityFlow: `/api/v1/intersections/{id}/plan`
  - Track performance
  - Auto-rollback if degradation detected
- **Output**: Applied configurations, performance logs

### Knowledge Base
- **What**: Shared state and history
- **Storage**: SQLite database (8 tables) + in-memory cache
- **Tables**: snapshots, graph_state, signal_configurations, phase_libraries, performance_metrics, adaptation_decisions, bandit_state, cycle_logs

---

## 📁 Project Structure

```
aegislights-controller/
├── main.py                     # Entry point - starts controller
├── run_visualizer.py           # Standalone web visualizer
├── requirements.txt            # Dependencies
│
├── config/                     # Configuration
│   ├── experiment.py          # Runtime settings
│   ├── mape.py                # MAPE parameters
│   ├── costs.py               # Cost coefficients
│   ├── simulator.py           # CityFlow connection
│   └── visualization.py       # Visualizer settings
│
├── adaptation_manager/         # MAPE-K implementation
│   ├── loop_controller.py     # Orchestration
│   ├── monitor.py             # CityFlow polling
│   ├── analyze.py             # Pattern detection
│   ├── plan.py                # Bandit planning
│   ├── execute.py             # Safe actuation
│   ├── knowledge.py           # Knowledge base
│   ├── bandit.py              # Contextual bandit
│   ├── safety_validator.py    # NEMA constraints
│   ├── rollback_manager.py    # Performance watchdog
│   └── metrics.py             # Performance calculation
│
├── graph_manager/              # Graph model
│   ├── graph_model.py         # Data structures
│   ├── graph_utils.py         # Algorithms, CityFlow integration
│   ├── graph_visualizer.py    # Web visualizer (Flask)
│   └── templates/
│       └── visualizer.html    # D3.js frontend
│
├── api/                        # CityFlow communication
│   ├── simulator_client.py    # HTTP client
│   ├── endpoints.py           # API methods
│   ├── data_schemas.py        # Pydantic models
│   └── example_input_format.py  # Data format docs
│
├── db_manager/                 # Database layer
│   ├── init_db.py             # Schema
│   ├── setup_db.py            # Setup script
│   ├── db_utils.py            # CRUD operations
│   └── cleanup_db.py          # Reset
│
└── tests/                      # Test suite (30+ tests)
```

---

## 🎨 Visualization

### Web-Based Visualizer (Port 5001)

**Features**:
- Real-time updates (2-second auto-refresh)
- Interactive D3.js force-directed graph
- Color-coded status (Green→Orange→Red)
- Live metrics dashboard
- Performance history charts
- Standalone operation (queries database)

**Usage**:

```bash
# Automatic (started by main.py if enable_web_visualizer=True)
python main.py

# Or standalone
python run_visualizer.py data/aegis_lights.db --host 0.0.0.0 --port 5001
```

**Access**: http://localhost:5001

**Elements**:
- **Nodes**: Blue (signalized A-E), Gray (virtual 1-8)
- **Edges**: Color by cost, width by queue
- **Metrics**: Cycle, delay, incidents, adaptations
- **Charts**: Cost trend, delay trend

---

## 🧪 Testing

```bash
conda activate aegis_lights

# All tests
pytest tests/ -v

# Passing tests (100%)
pytest tests/test_analyze.py -v       # 8/8
pytest tests/test_execute.py -v      # 4/4
pytest tests/test_graph_export_viz.py -v  # 8/8

# With coverage
pytest tests/ --cov=. --cov-report=html
```

---

## 🔧 How It Works

### Complete MAPE Cycle (Every 60 seconds)

```
1. MONITOR (5-10s)
   ├─ GET http://localhost:5000/api/v1/snapshots/latest
   ├─ Aggregate lanes → edges
   ├─ Update graph_state table
   └─ Store snapshot

2. ANALYZE (2-5s)
   ├─ Compute edge costs
   ├─ Identify hotspots (>70th percentile)
   ├─ Find k=3 bypass routes
   └─ Determine targets

3. PLAN (5-10s)
   ├─ Build context features
   ├─ Query phase library
   ├─ Bandit selection (UCB)
   ├─ Calculate offsets
   └─ Create adaptations

4. EXECUTE (2-5s)
   ├─ Validate safety (NEMA)
   ├─ POST /api/v1/intersections/{id}/plan
   ├─ Check performance
   └─ Rollback if degraded

Total: 15-30 seconds
Wait: 30-45 seconds until next cycle
```

---

## 🛠️ Troubleshooting

**Cannot connect to simulator**
```bash
# Check CityFlow is running
curl http://localhost:5000/health

# Start CityFlow if needed
cd cityflow/script
python main.py
```

**Database not found**
```bash
conda activate aegis_lights
python db_manager/setup_db.py
```

**Flask not found**
```bash
conda activate aegis_lights
pip install flask flask-cors
```

**Visualizer port in use**
```bash
# Change port
python run_visualizer.py data/aegis_lights.db --port 5002
```

**Controller stops unexpectedly**
- Check CityFlow is still running
- Check simulator logs for errors
- Verify network connectivity

---

## 📚 Additional Documentation

- `WEB_VISUALIZER_GUIDE.md` - Web visualizer docs
- `VISUALIZER_QUICKSTART.md` - Visualizer quick start
- `DATABASE_SCHEMA_REFERENCE.md` - SQL reference
- `SYSTEM_VERIFICATION.md` - Architecture verification
- `QUICKSTART.md` - Quick start guide

---

## 🎓 Research Applications

### Research Questions

**RQ1**: Performance vs fixed-time baseline?
- Metrics: Avg trip time, P95, throughput
- Hypothesis: 15-25% improvement

**RQ2**: Incident-aware planning benefits?
- Metrics: Clearance time, spillback frequency  
- Hypothesis: 30-40% faster clearance

**RQ3**: Bandit learning improvement?
- Metrics: Reward progression
- Hypothesis: Monotonic improvement

### Running Experiments

```bash
# 1. Configure CityFlow (cityflow/net_config/)
# 2. Set experiment params (config/experiment.py)
# 3. Run controller
conda activate aegis_lights
python main.py

# 4. Let run for N hours
# 5. Export data
python -c "from db_manager import export_experiment_data; ..."

# 6. Analyze results
```

---

## 🎉 Summary

AegisLights: Production-ready adaptive traffic control with CityFlow

✅ **Continuous Adaptation** - Runs indefinitely, adapts every 60s  
✅ **Learns from Experience** - Contextual bandit improves over time  
✅ **Safety Guaranteed** - NEMA validation + auto-rollback  
✅ **Real-time Visualization** - Web interface with D3.js  
✅ **Fully Tested** - 30+ tests, core logic 100%  
✅ **Production Ready** - Logging, error handling, graceful shutdown  

**Start Now**: Launch CityFlow, then run `python main.py`

---

*Version: 2.0 | Updated: November 23, 2025 | Status: Production Ready*
