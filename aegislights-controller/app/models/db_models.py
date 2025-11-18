from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer

from app.core.db import Base


class CycleMetricRecord(Base):
    __tablename__ = "cycle_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    avg_trip_time_s = Column(Float, nullable=True)
    p95_trip_time_s = Column(Float, nullable=True)
    total_spillbacks = Column(Integer, nullable=True)
    incident_count = Column(Integer, nullable=True)
