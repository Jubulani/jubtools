import os
import tempfile
from datetime import datetime

import aiosqlite
import pytest
from async_asgi_testclient import TestClient
from pydantic import BaseModel

from jubtools import config, db
from jubtools.errors import ClientError
from jubtools.systemtools import DBModule, create_fastapi_app


class UserNotFound(ClientError):
    http_status = 404

    def __init__(self, user_id: int):
        super().__init__(f"User not found (id={user_id})")


class User(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime


@pytest.fixture(scope="session")
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

        db.store(
            __name__ + ":get_all_users", "SELECT id, name, email, created_at FROM users ORDER BY id"
        )
        db.store(
            __name__ + ":get_user", "SELECT id, name, email, created_at FROM users WHERE id = {id}"
        )

        # Add endpoint to return user data
        @app.get("/users")
        async def get_users():
            users = await db.execute(__name__ + ":get_all_users")
            return {"users": [User(**user) for user in users]}

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            rs = await db.execute(__name__ + ":get_user", {"id": user_id})
            if not len(rs):
                raise UserNotFound(user_id)
            return {"user": User(**rs[0])}

        # Create test client
        async with TestClient(application=app) as client:
            yield client


class TestIntegrationWithRealDatabase:
    """Integration tests using real SQLite database."""

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

    async def test_get_nonexistent_user(self, integration_client):
        """Test retrieving a user that doesn't exist."""
        response = await integration_client.get("/users/999")
        assert response.status_code == 404

        assert response.json() == {"error": {"message": "User not found (id=999)"}}
