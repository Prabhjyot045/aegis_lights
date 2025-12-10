# AegisLights Controller

**Self-Adaptive Traffic Signal Control using MAPE-K with CityFlow Simulator**

---

## Overview

AegisLights implements a MAPE-K (Monitor-Analyze-Plan-Execute-Knowledge) control loop that continuously adapts traffic signal timing to minimize average trip time. The controller connects to a CityFlow traffic simulator and uses a contextual bandit algorithm for decision-making.

**Key Features:**
- Real-time traffic monitoring from CityFlow
- Predictive analysis using trend forecasting and queue penalties
- Contextual bandit (UCB/Thompson Sampling) for plan selection
- Automatic incident detection and response
- Web-based visualization dashboard
- Experimental comparison tools

---

## Quick Start

### 1. Setup Environment

```bash
cd aegislights-controller

# Create conda environment from environment.yml
conda env create -f environment.yml

# Activate environment
conda activate aegis_lights
```

### 2. Initialize Database

```bash
conda activate aegis_lights
python db_manager/setup_db.py
```

### 3. Start CityFlow Simulator (separate terminal)

```bash
cd ../cityflow/script
python main.py
```

### 4. Run Controller (seperate terminal)

```bash
conda activate aegis_lights
python main.py
```

### 5. View Dashboard

Open http://localhost:5001 in your browser.

---

## Running Experiments

### Control Baseline (No Adaptation)

Collect baseline data without any signal adaptations:

```bash
# Run for 360 seconds (3600 simulation steps at 0.1s/step)
python control_baseline.py --duration 360 --output data/baseline.csv
```

### Experimental Run (With MAPE-K Adaptation)

```bash
# Reset database for fresh experiment
python db_manager/cleanup_db.py
python db_manager/setup_db.py

# Run controller (data saved to database automatically)
python main.py
```

### Generate Comparison Graph

Compare control vs experimental results:

```bash
python plot_comparison.py \
    --control data/baseline.csv \
    --db data/aegis_lights.db \
    --output output/comparison.png
```

---

## Database Management

### Reset Database
Delete the data/aegis_lights.db and setup again.

```bash
python db_manager/setup_db.py
```

### Export Data

Data is automatically exported to `output/experiments/` when the controller stops.

---

## Visualization

### Start with Controller (Default)

The web visualizer starts automatically with `main.py` on port 5001.

### Standalone Visualizer

```bash
python run_visualizer.py data/aegis_lights.db --port 5001
```

### Access Dashboard

- URL: http://localhost:5001
- Features: Live graph, metrics, trend charts
- Auto-refresh: Every 5 seconds

---

## Configuration

### MAPE Loop Settings (`config/mape.py`)

```python
cycle_period_seconds = 3      # How often to adapt
bandit_algorithm = "ucb"      # or "thompson_sampling"
exploration_factor = 0.2      # Bandit exploration rate
```

### Simulator Connection (`config/simulator.py`)

```python
host = "localhost"
port = 5000
```

### Experiment Settings (`config/experiment.py`)

```python
max_duration_seconds = None   # None = run indefinitely
enable_web_visualizer = True
```

---

## Project Structure

```
aegislights-controller/
├── main.py                 # Entry point
├── control_baseline.py     # Baseline data collection
├── plot_comparison.py      # Generate comparison graphs
├── run_visualizer.py       # Standalone visualizer
│
├── adaptation_manager/     # MAPE-K implementation
│   ├── loop_controller.py  # Main orchestration
│   ├── monitor.py          # Data collection from CityFlow
│   ├── analyze.py          # Trend prediction & hotspot detection
│   ├── plan.py             # Bandit-based plan selection
│   ├── execute.py          # Apply signal changes
│   ├── knowledge.py        # Database interface
│   ├── bandit.py           # Contextual bandit algorithm
│   └── metrics.py          # Performance calculation
│
├── graph_manager/          # Traffic network model
│   ├── graph_model.py      # Node/Edge data structures
│   ├── graph_utils.py      # CityFlow data transformation
│   └── graph_visualizer.py # Flask web server + D3.js
│
├── api/                    # CityFlow communication
│   ├── simulator_client.py # HTTP client
│   ├── endpoints.py        # API methods
│   └── data_schemas.py     # Data models
│
├── db_manager/             # Database layer
│   ├── setup_db.py         # Initialize database
│   ├── cleanup_db.py       # Reset database
│   └── db_utils.py         # CRUD operations
│
├── config/                 # Configuration files
│   ├── mape.py             # MAPE loop settings
│   ├── simulator.py        # CityFlow connection
│   └── experiment.py       # Runtime settings
│
└── data/                   # Database storage
    └── aegis_lights.db     # SQLite database
```

---

## MAPE-K Loop

Each cycle (default 3 seconds):

1. **Monitor**: Query CityFlow for traffic state (queues, delays, incidents)
2. **Analyze**: Identify hotspots, predict trends, find bypass routes
3. **Plan**: Select optimal signal phases using contextual bandit
4. **Execute**: Apply phase changes to CityFlow intersections
5. **Knowledge**: Store metrics and update bandit rewards

### Reward Function (Optimization Objective)

```python
reward = -avg_trip_time - (spillbacks * 50) - (avg_queue * 2.0)
```

- Primary: Minimize average trip time
- Predictive: Queue penalty prevents future congestion
- Safety: Heavy spillback penalty

---

## Troubleshooting

### Cannot connect to simulator
```bash
curl http://localhost:5000/health
# If fails, start CityFlow: cd ../cityflow/script && python main.py
```

### Database not found
```bash
python db_manager/setup_db.py
```

### Port 5001 in use
```bash
lsof -ti:5001 | xargs kill -9
```

### Port 5000 in use (simulator)
```bash
lsof -ti:5000 | xargs kill -9
```

---

## Testing

```bash
conda activate aegis_lights
pytest tests/ -v
```

---

## Network Topology

CityFlow simulates a 5-intersection grid:

```
    1           3
    ↓           ↓
┌───A───┐   ┌───B───┐
│  🚦   │──→│  🚦   │→4
└───┬───┘   └───┬───┘
    │           │
┌───C───┐   ┌───D───┐
│  🚦   │←──│  🚦   │→7
└───┬───┘   └───┬───┘
    │           
┌───E───┐       8
│  🚦   │
└───────┘
    ↓
    6

🚦 = Signalized intersection (A-E)
1-8 = Virtual entry/exit nodes
```

- 5 signalized intersections
- 8 virtual nodes
- 28 directed edges
- 4 signal phases per intersection

---

*ECE 750 - Self-Adaptive Systems*
