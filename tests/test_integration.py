import os
import tempfile

import aiosqlite
import pytest
import pytest_asyncio
from async_asgi_testclient import TestClient

from jubtools import config, db
from jubtools.systemtools import DBModule, create_fastapi_app


@pytest_asyncio.fixture
async def integration_client():
    """Create a FastAPI client with real SQLite database for integration testing."""

    # Create temporary directory for test database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")

        # Configure the application
        config.CONFIG = {
            "app_name": "IntegrationTestApp",
            "fastapi": {"disable_docs": False},
            "db": {"sqlite": {"path": db_path}},
        }

        # Initialize database and create test data
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                INSERT INTO users (name, email) VALUES 
                ('John Doe', 'john@example.com'),
                ('Jane Smith', 'jane@example.com'),
                ('Bob Johnson', 'bob@example.com')
            """)
            await conn.commit()

        # Create FastAPI app with SQLite database
        app = create_fastapi_app(env="test", version="1.0.0", db_module=DBModule.SQLITE)

        # Initialize database module
        await db.init(DBModule.SQLITE)

        # Add endpoint to return user data
        @app.get("/users")
        async def get_users():
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM users ORDER BY id")
                rows = await cursor.fetchall()
                return {"users": [dict(row) for row in rows]}

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            from fastapi import HTTPException

            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                return {"user": dict(row)}

        # Create test client
        async with TestClient(application=app) as client:
            yield client


@pytest_asyncio.fixture
async def integration_client_with_stored_queries():
    """Create a FastAPI client with stored SQL queries for integration testing."""

    # Create temporary directory for test database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")

        # Configure the application
        config.CONFIG = {
            "app_name": "IntegrationTestApp",
            "fastapi": {"disable_docs": False},
            "db": {"sqlite": {"path": db_path}},
        }

        # Initialize database and create test data
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("""
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    category TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                INSERT INTO products (name, price, category) VALUES
                ('Laptop', 999.99, 'Electronics'),
                ('Book', 29.99, 'Education'),
                ('Coffee Mug', 12.99, 'Kitchen')
            """)
            await conn.commit()

        # Create FastAPI app with SQLite database
        app = create_fastapi_app(env="test", version="1.0.0", db_module=DBModule.SQLITE)

        # Initialize database module
        db.init(DBModule.SQLITE)

        # Clear any existing stored queries to avoid conflicts
        from jubtools import sqlt

        sqlt._SAVED_SQL.clear()

        # Store SQL queries using the db.store method
        db.store("get_all_products", "SELECT * FROM products ORDER BY id")
        db.store("get_product_by_id", "SELECT * FROM products WHERE id = ?")
        db.store(
            "get_products_by_category", "SELECT * FROM products WHERE category = ? ORDER BY name"
        )

        # Add endpoints that use stored queries and direct database access
        @app.get("/products")
        async def get_products():
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM products ORDER BY id")
                rows = await cursor.fetchall()
                return {"products": [dict(row) for row in rows]}

        @app.get("/products/{product_id}")
        async def get_product(product_id: int):
            from fastapi import HTTPException

            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Product not found")
                return {"product": dict(row)}

        @app.get("/products/category/{category}")
        async def get_products_by_category(category: str):
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM products WHERE category = ? ORDER BY name", (category,)
                )
                rows = await cursor.fetchall()
                return {"products": [dict(row) for row in rows]}

        # Create test client
        async with TestClient(application=app) as client:
            yield client


@pytest_asyncio.fixture
async def health_client():
    """Simple client for testing the built-in health endpoint."""
    config.CONFIG = {"app_name": "HealthTestApp", "fastapi": {"disable_docs": False}}
    app = create_fastapi_app(env="test", version="1.0.0")

    async with TestClient(application=app) as client:
        yield client


class TestIntegrationWithRealDatabase:
    """Integration tests using real SQLite database."""

    @pytest.mark.asyncio
    async def test_get_all_users(self, integration_client):
        """Test retrieving all users from database."""
        response = await integration_client.get("/users")
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert len(data["users"]) == 3

        # Verify first user data
        user1 = data["users"][0]
        assert user1["id"] == 1
        assert user1["name"] == "John Doe"
        assert user1["email"] == "john@example.com"
        assert "created_at" in user1

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, integration_client):
        """Test retrieving a specific user by ID."""
        response = await integration_client.get("/users/2")
        assert response.status_code == 200

        data = response.json()
        assert "user" in data
        user = data["user"]
        assert user["id"] == 2
        assert user["name"] == "Jane Smith"
        assert user["email"] == "jane@example.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, integration_client):
        """Test retrieving a user that doesn't exist."""
        response = await integration_client.get("/users/999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert data["detail"] == "User not found"


class TestIntegrationWithStoredQueries:
    """Integration tests using stored SQL queries."""

    @pytest.mark.asyncio
    async def test_get_all_products(self, integration_client_with_stored_queries):
        """Test retrieving all products using stored query."""
        response = await integration_client_with_stored_queries.get("/products")
        assert response.status_code == 200

        data = response.json()
        assert "products" in data
        assert len(data["products"]) == 3

        # Verify product data
        laptop = data["products"][0]
        assert laptop["name"] == "Laptop"
        assert laptop["price"] == 999.99
        assert laptop["category"] == "Electronics"

    @pytest.mark.asyncio
    async def test_get_product_by_id(self, integration_client_with_stored_queries):
        """Test retrieving a specific product by ID using stored query."""
        response = await integration_client_with_stored_queries.get("/products/2")
        assert response.status_code == 200

        data = response.json()
        assert "product" in data
        product = data["product"]
        assert product["name"] == "Book"
        assert product["price"] == 29.99
        assert product["category"] == "Education"

    @pytest.mark.asyncio
    async def test_get_products_by_category(self, integration_client_with_stored_queries):
        """Test retrieving products by category using stored query."""
        response = await integration_client_with_stored_queries.get(
            "/products/category/Electronics"
        )
        assert response.status_code == 200

        data = response.json()
        assert "products" in data
        assert len(data["products"]) == 1
        assert data["products"][0]["name"] == "Laptop"

    @pytest.mark.asyncio
    async def test_get_products_empty_category(self, integration_client_with_stored_queries):
        """Test retrieving products from empty category."""
        response = await integration_client_with_stored_queries.get("/products/category/Sports")
        assert response.status_code == 200

        data = response.json()
        assert "products" in data
        assert len(data["products"]) == 0


class TestBuiltInHealthEndpoint:
    """Test the built-in health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, health_client):
        """Test the built-in health endpoint."""
        response = await health_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "request_ts" in data
        assert data["status"] == "UP"
        assert "uptime" in data
        assert data["version"] == "1.0.0"
        assert data["env"] == "test"
