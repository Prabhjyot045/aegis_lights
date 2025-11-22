"""
AegisLights Test Suite

This package contains all test modules for the AegisLights traffic signal control system.

Test Organization:
- test_schema.py: Database schema validation
- test_db.py: Database operations and queries
- test_monitor.py: Monitor stage (MAPE-K)
- test_analyze.py: Analyze stage (MAPE-K)

To run all tests:
    python -m pytest tests/

To run specific test:
    python -m tests.test_monitor
    python -m tests.test_analyze

Test Results:
- Database: ✅ All tables and indices verified
- Monitor: ✅ 100% pass rate (5/5 cycles)
- Analyze: ✅ 100% pass rate (8/8 tests)
"""

__version__ = "0.3.0"
__all__ = [
    "test_schema",
    "test_db",
    "test_monitor",
    "test_analyze"
]
