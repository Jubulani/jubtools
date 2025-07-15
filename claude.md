# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

jubtools is a Python package containing shared utility tools for personal work. It's a collection of helpful modules including:

- config.py: Configuration management with TOML file loading and nested key access
- db.py: Unified database interface that wraps both PostgreSQL and SQLite modules
- httptools.py: HTTP client utilities with response format handling (JSON, CSV, bytes)
- misctools.py: Utility classes like a Timer context manager
- psql.py: PostgreSQL utilities
- sqlt.py: SQLite utilities
- systemtools.py: System-level utilities

The package uses FastAPI as its main dependency and includes testing support.

## Development Commands

### Testing
- Run tests: `uv run pytest`

### Building and Publishing
- Build package: `python -m build`
- Clean dist directory: `rm -r dist`
- Upload to PyPI: `twine upload dist/*`
- Full release process: `./release.sh`

### Package Management
- Install build dependencies: `pip install build twine`

## Architecture Overview

### Core Module Structure
- All modules are in the `jubtools/` directory
- Each module is self-contained with specific functionality
- Common logging pattern using `logging.getLogger(__name__)`

### Configuration System (config.py)
- Uses TOML files for configuration
- Supports environment-specific configs in `config/env/` directory
- Base config loaded from `config/base.toml`
- Nested key access with dot notation (e.g., `config.get("db.port")`)
- Case-insensitive key handling

### Database Integration
- **Unified Interface (db.py)**: Primary interface for database operations that automatically delegates to the appropriate database module
- **PostgreSQL (psql.py)**: Full-featured PostgreSQL support with connection pooling, transactions, and context variables
- **SQLite (sqlt.py)**: Basic SQLite support (note: incomplete implementation compared to PostgreSQL)
- Connection pooling and middleware integration for FastAPI
- Custom Row classes that support dot notation access
- Context variable pattern for connection management (PostgreSQL)
- Named SQL query storage system

#### Using the Unified Database Interface
```python
import jubtools.db as db
from jubtools.systemtools import DBModule

# Initialize for PostgreSQL
await db.init(DBModule.POSTGRES)

# Initialize for SQLite  
db.init(DBModule.SQLITE)

# Common operations (works with both databases)
db.store("get_user", "SELECT * FROM users WHERE id = {user_id}")
async with db.connect():
    result = await db.execute("get_user", {"user_id": 123})
    rows = await db.execute_sql("SELECT COUNT(*) FROM users")

# Get appropriate middleware
middleware = db.get_middleware()
```

**Important**: The SQLite module (sqlt.py) currently has limited functionality compared to PostgreSQL. The unified interface will raise `DatabaseError` for unimplemented SQLite operations like `execute()`, `execute_sql()`, `connect()`, and `transaction()`.

### FastAPI Integration (systemtools.py)
- `create_fastapi_app()` function creates pre-configured FastAPI instances
- Built-in health endpoint at `/health`
- Automatic CORS middleware setup based on config
- Request timing middleware with logging
- Database middleware auto-configuration based on DBModule enum

### Testing Setup
- Uses pytest with async support (pytest-asyncio)
- Test client configured with `async_asgi_testclient`
- Configuration fixture for testing different config scenarios
- Session-scoped client fixture for FastAPI testing

### Key Patterns
- Context managers for timing (Timer class)
- Middleware pattern for database connections
- Environment variable for sensitive data (e.g., PG_PASSWORD)
- Logging throughout with consistent formatting
- Error handling with custom exception types