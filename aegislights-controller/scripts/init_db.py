"""Create local SQLite database tables."""

from app.core.db import init_db
from app.core.logging import configure_logging


if __name__ == "__main__":
    configure_logging()
    init_db()
    print("Database initialized.")
