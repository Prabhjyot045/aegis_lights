# AegisLights Quick Start Guide

**Get up and running with AegisLights in 10 minutes**

---

## ⚡ Prerequisites

- **Python 3.10+** (conda recommended)
- **CityFlow simulator** running on `localhost:5000`
- **Linux/WSL** environment (tested on Ubuntu)

---

## 🚀 Fast Setup

### 1. Create Conda Environment

```bash
cd aegislights-controller

# Create environment
conda create -n aegis_lights python=3.10
conda activate aegis_lights

# Install dependencies
pip install -r requirements.txt
pip install flask flask-cors
```

**⚠️ CRITICAL**: Always activate `aegis_lights` environment before running ANY Python command!

---

### 2. Setup Database

```bash
conda activate aegis_lights
python db_manager/setup_db.py
```

Creates `data/aegis_lights.db` with 8 tables. Should complete in ~1 second.

**Verify**:
```bash
ls -lh data/aegis_lights.db
# Should show ~40 KB file
```

---

### 3. Initialize Phase Library

```bash
conda activate aegis_lights
python db_manager/init_phase_library.py
```

Populates the database with default CityFlow signal timing plans for all 5 signalized intersections (A-E). Creates 3 plans per intersection:
- **NS Priority**: Phase 0 - North-South movements prioritized
- **EW Priority**: Phase 2 - East-West movements prioritized  
- **Balanced**: Phase 0/2 - Equal priority

**Expected output**:
```
✓ Phase library initialized
✓ Default plans loaded successfully

Signal timing plans created:
  Intersection A: 3 plans
    - 2phase_ns_priority (Phase 0)
    - 2phase_ew_priority (Phase 2)
    - 2phase_balanced (Phase 0)
  ...
✓ Phase library ready for use! 🚦
```

---

### 4. Start CityFlow Simulator

```bash
# In separate terminal
cd /home/prab/ws/ECE750/aegis_lights/cityflow/script
python main.py
```

**Verify**:
```bash
curl http://localhost:5000/health
# Should return: {"status": "ok", "service": "cityflow"}
```

**Expected console output**:
```
Step 0
Step 1
Step 2
...
```
(Steps print every 0.1 seconds = 10x simulation speed)

CityFlow provides:
- 5 signalized intersections (A-E)
- 8 virtual nodes (1-8)
- 28 directed edges
- 4-phase timing control per intersection (30s/10s/30s/10s)

---

### 5. Run Controller

```bash
# ALWAYS activate conda first!
conda activate aegis_lights
python main.py
```

**Expected Output**:
```
2024-11-23 15:30:00 INFO     Starting AegisLights Controller
2024-11-23 15:30:01 INFO     Connected to CityFlow at http://localhost:5000
2024-11-23 15:30:02 INFO     Web visualizer started at http://localhost:5001
2024-11-23 15:30:03 INFO     MAPE loop started (5-second cycles)
2024-11-23 15:30:03 INFO     Running indefinitely until simulator stops or Ctrl+C
2024-11-23 15:30:05 INFO     [Cycle 1] MONITOR: Retrieved 28 edges, 5 signals
2024-11-23 15:30:06 INFO     [Cycle 1] ANALYZE: Found 3 hotspots
2024-11-23 15:30:07 INFO     [Cycle 1] PLAN: Selected 2 adaptations
2024-11-23 15:30:08 INFO     [Cycle 1] EXECUTE: Applied 2/2 successfully
2024-11-23 15:30:13 INFO     [Cycle 2] Starting...
```

Controller will:
- Run **indefinitely** (until CityFlow stops or you press Ctrl+C)
- Adapt signals every **5 seconds** (configurable in `config/mape.py`)
- Log all actions to console + database

---

### 6. View Visualization

Open browser: **http://localhost:5001**

You'll see:
- **Interactive graph**: Drag nodes, zoom, pan
- **Live metrics**: Cycle count, delays, incidents
- **Auto-refresh**: Updates every 2 seconds
- **Color coding**: Green (good) → Orange (moderate) → Red (severe)

---

## ⚙️ Basic Configuration

**Current Speed Settings (Fast Experimentation Mode)**:
- **Simulator**: 0.1s per step = 10x real-time (10 simulation seconds per real second)
- **Controller**: 5-second MAPE cycles = 12 adaptations per minute
- **Result**: 1 hour real time = 10 hours simulated traffic

Edit these files to change timing:

### Change Controller Cycle Period

Edit `config/mape.py`:
```python
cycle_period_seconds: int = 10  # Was 5 (faster = more frequent, slower = less overhead)
```

### Change Simulator Speed

Edit `cityflow/script/args.json`:
```json
{
  "steps_interval": 0.5,  // Was 0.1 (larger = slower, more realistic)
  ...
}
```

### Set Fixed Duration

Edit `config/experiment.py`:
```python
max_duration_seconds: int = 3600  # 1 hour (was None)
```

### Adjust Bandit Exploration

Edit `config/mape.py`:
```python
exploration_factor: float = 0.3  # More exploration (was 0.2)
```

### Connect Different CityFlow Port

Edit `config/simulator.py`:
```python
port: int = 5001  # Was 5000
```

---

## 🎨 Visualization Options

### Web Visualizer (Recommended)

```bash
# Started automatically by main.py
# Or run standalone:
conda activate aegis_lights
python run_visualizer.py data/aegis_lights.db --host 0.0.0.0 --port 5001
```

**Access**: http://localhost:5001  
**Features**: Real-time, interactive, no compilation

### Disable Web Visualizer

Edit `config/experiment.py`:
```python
enable_web_visualizer: bool = False
```

---

## 🧪 Testing

```bash
conda activate aegis_lights

# Quick test
pytest tests/test_analyze.py -v

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=adaptation_manager --cov-report=html
```

**Expected**:
- 30+ tests
- All passing
- ~80% coverage

---

## 🔧 Troubleshooting

### Problem: "Cannot connect to simulator"

**Solution**:
```bash
# Check CityFlow is running
curl http://localhost:5000/health

# If not, start it:
cd cityflow_aegis_light/script
python main.py
```

---

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution**:
```bash
conda activate aegis_lights
pip install flask flask-cors
```

---

### Problem: "sqlite3.OperationalError: no such table"

**Solution**:
```bash
conda activate aegis_lights
python db_manager/setup_db.py
```

---

### Problem: "No valid plans found for intersection X" or "Phase library empty"

**Solution**: Phase library not initialized
```bash
conda activate aegis_lights
python db_manager/init_phase_library.py
```

This creates default signal timing plans for all 5 intersections (A-E).

---

### Problem: "Address already in use (port 5001)"

**Solution**:
```bash
# Find process using port
lsof -i :5001

# Kill it
kill -9 <PID>

# Or change port
python run_visualizer.py data/aegis_lights.db --port 5002
```

---

### Problem: "Controller stops after 1 cycle"

**Possible causes**:
- CityFlow crashed/stopped
- Network connectivity issue
- Database locked

**Debug**:
```bash
# Check CityFlow logs
cd cityflow_aegis_light/script
tail -f cityflow.log

# Check controller logs
cd aegislights-controller
tail -f aegis_lights.log
```

---

## 📊 Quick Data Export

```bash
conda activate aegis_lights
python -c "
from db_manager.db_utils import export_metrics_csv
export_metrics_csv('data/aegis_lights.db', 'results.csv')
"
```

Creates `results.csv` with:
- Cycle number, timestamp
- Average delay, max queue
- Incidents, adaptations
- Performance scores

---

## 🎯 Typical Usage Patterns

### Pattern 1: Development/Testing (Short Run)

```python
# config/experiment.py
max_duration_seconds: int = 300  # 5 minutes
enable_web_visualizer: bool = True
```

```bash
conda activate aegis_lights
python main.py
# Open http://localhost:5001
# Watch 5 cycles (300s / 60s = 5)
```

---

### Pattern 2: Long Experiment (Hours)

```python
# config/experiment.py
max_duration_seconds: int = None  # Indefinite
enable_web_visualizer: bool = False  # Reduce overhead
```

```bash
conda activate aegis_lights
nohup python main.py > experiment.log 2>&1 &

# Check progress
tail -f experiment.log

# Stop gracefully
pkill -SIGINT -f main.py
```

---

### Pattern 3: Real-Time Monitoring Only

```bash
# Start visualizer standalone (no controller)
conda activate aegis_lights
python run_visualizer.py data/aegis_lights.db --host 0.0.0.0 --port 5001

# Access from browser
# Shows historical data + live if controller running elsewhere
```

---

## 📈 What to Watch

### Good Signs
- ✅ Cycles completing every 5s (or configured period)
- ✅ Average delay decreasing over time
- ✅ Adaptations applied successfully
- ✅ No rollbacks (or very few)
- ✅ Bandit reward increasing

### Warning Signs
- ⚠️ Delays increasing consistently
- ⚠️ Frequent rollbacks (>20%)
- ⚠️ Adaptations failing
- ⚠️ No hotspots detected (inactive analyzer)
- ⚠️ Bandit reward flat/decreasing

### Critical Issues
- ❌ Controller stops unexpectedly
- ❌ CityFlow not responding
- ❌ Database errors
- ❌ Validation failures

---

## 🎓 Next Steps

1. **Read Full Documentation**: `README.md`
2. **Explore Visualizer**: `WEB_VISUALIZER_GUIDE.md`
3. **Understand Database**: `DATABASE_SCHEMA_REFERENCE.md`
4. **Verify System**: `SYSTEM_VERIFICATION.md`
5. **Run Experiments**: Design scenarios in CityFlow config

---

## 📋 Checklist

Before starting experiment:
- [ ] Conda environment `aegis_lights` activated
- [ ] Database setup complete (`data/aegis_lights.db` exists)
- [ ] Phase library initialized (`python db_manager/init_phase_library.py` run)
- [ ] CityFlow running (`curl http://localhost:5000/health` works)
- [ ] Configuration reviewed (`config/*.py`)
- [ ] Simulator timing configured (`cityflow/script/args.json`)
- [ ] Visualizer port free (5001 or custom)
- [ ] Disk space available (logs + database growth)

During experiment:
- [ ] Monitor visualizer for anomalies
- [ ] Check logs periodically
- [ ] Track performance trends
- [ ] Verify CityFlow stability

After experiment:
- [ ] Export data (`db_manager/db_utils.py`)
- [ ] Analyze results
- [ ] Clean database if needed (`cleanup_db.py`)

---

## 🎉 Summary

**Minimal Working Setup**:
```bash
# 1. Create environment
conda create -n aegis_lights python=3.10
conda activate aegis_lights
pip install -r requirements.txt flask flask-cors

# 2. Setup database & phase library
python db_manager/setup_db.py
python db_manager/init_phase_library.py

# 3. Start CityFlow (separate terminal)
cd /home/prab/ws/ECE750/aegis_lights/cityflow/script
python main.py

# 4. Start controller (back in aegislights-controller directory)
cd /home/prab/ws/ECE750/aegis_lights/aegislights-controller
python main.py

# 5. View results
# Browser: http://localhost:5001
```

**That's it!** Controller adapts every 5 seconds (50 simulation steps), visualizer updates every 2 seconds.

---

**Questions?** See `README.md` or check logs in console.

*Quick Start Guide | Updated: November 23, 2025*
