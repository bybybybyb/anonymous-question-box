# SQLite WAL and single-writer for Python

The Python backend enables `PRAGMA journal_mode=WAL` and `busy_timeout=5000` on connect. Run one uvicorn worker per database file during initial cutover. Do not run Go and Python writers against the same SQLite file simultaneously in production or soak tests; use DB copies for parity tests.
