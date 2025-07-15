from unittest.mock import AsyncMock, Mock, patch

import pytest

from jubtools import db
from jubtools.systemtools import DBModule


class TestDatabaseUnifiedInterface:
    """Test the unified database interface"""

    def test_init_postgres(self):
        """Test initialization with PostgreSQL"""
        # Reset global state
        db._db_module = None
        db._psql = None

        # Mock the import to avoid loading the real psql module
        with patch.dict("sys.modules", {"jubtools.psql": Mock()}):
            with patch("jubtools.db.psql", create=True) as mock_psql_module:
                mock_psql_module.init = Mock(return_value=None)
                result = db.init(DBModule.POSTGRES)
                assert db.get_active_module() == DBModule.POSTGRES
                assert db.is_initialized() is True
                # The result should be the return value of psql.init()
                assert result is not None  # We expect a Mock object

    def test_init_sqlite(self):
        """Test initialization with SQLite"""
        with patch("jubtools.db._sqlt"):
            db.init(DBModule.SQLITE)
            assert db.get_active_module() == DBModule.SQLITE
            assert db.is_initialized() is True

    def test_store_postgres(self):
        """Test storing SQL with PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            db._db_module = DBModule.POSTGRES
            db.store("test_query", "SELECT * FROM users")
            mock_psql.store.assert_called_once_with("test_query", "SELECT * FROM users")

    def test_store_sqlite(self):
        """Test storing SQL with SQLite"""
        with patch("jubtools.db._sqlt") as mock_sqlt:
            db._db_module = DBModule.SQLITE
            db.store("test_query", "SELECT * FROM users")
            mock_sqlt.store.assert_called_once_with("test_query", "SELECT * FROM users")

    def test_store_not_initialized(self):
        """Test storing SQL when not initialized"""
        db._db_module = None
        with pytest.raises(db.DatabaseError):
            db.store("test_query", "SELECT * FROM users")

    def test_get_middleware_postgres(self):
        """Test getting middleware for PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            mock_psql.ConnMiddleware = Mock()
            db._db_module = DBModule.POSTGRES
            middleware = db.get_middleware()
            assert middleware == mock_psql.ConnMiddleware

    def test_get_middleware_sqlite(self):
        """Test getting middleware for SQLite"""
        with patch("jubtools.db._sqlt") as mock_sqlt:
            mock_sqlt.ConnMiddleware = Mock()
            db._db_module = DBModule.SQLITE
            middleware = db.get_middleware()
            assert middleware == mock_sqlt.ConnMiddleware

    def test_get_middleware_not_initialized(self):
        """Test getting middleware when not initialized"""
        db._db_module = None
        with pytest.raises(db.DatabaseError):
            db.get_middleware()

    def test_row_wrapper(self):
        """Test the Row wrapper functionality"""
        # Mock a database row
        mock_row = Mock()
        mock_row.id = 1
        mock_row.name = "test"
        mock_row.__getitem__ = Mock(return_value="test_value")
        mock_row.__contains__ = Mock(return_value=True)
        mock_row.keys = Mock(return_value=["id", "name"])
        mock_row.values = Mock(return_value=[1, "test"])
        mock_row.items = Mock(return_value=[("id", 1), ("name", "test")])

        # Wrap it with our unified Row
        row = db.Row(mock_row)

        # Test attribute access
        assert row.id == 1
        assert row.name == "test"

        # Test item access
        assert row["key"] == "test_value"
        mock_row.__getitem__.assert_called_with("key")

        # Test contains
        assert "key" in row
        mock_row.__contains__.assert_called_with("key")

        # Test keys, values, items
        assert row.keys() == ["id", "name"]
        assert row.values() == [1, "test"]
        assert row.items() == [("id", 1), ("name", "test")]

    @pytest.mark.asyncio
    async def test_execute_postgres(self):
        """Test executing stored query with PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            mock_row = Mock()
            mock_psql.execute = AsyncMock(return_value=[mock_row])
            db._db_module = DBModule.POSTGRES

            result = await db.execute("test_query", {"param": "value"})

            mock_psql.execute.assert_called_once_with("test_query", {"param": "value"}, True)
            assert len(result) == 1
            assert isinstance(result[0], db.Row)

    @pytest.mark.asyncio
    async def test_execute_sqlite_not_implemented(self):
        """Test executing stored query with SQLite (not implemented)"""
        with patch("jubtools.db._sqlt"):
            db._db_module = DBModule.SQLITE

            with pytest.raises(db.DatabaseError, match="SQLite execute function not implemented"):
                await db.execute("test_query")

    @pytest.mark.asyncio
    async def test_execute_sql_postgres(self):
        """Test executing raw SQL with PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            mock_row = Mock()
            mock_psql.execute_sql = AsyncMock(return_value=[mock_row])
            db._db_module = DBModule.POSTGRES

            result = await db.execute_sql("SELECT * FROM users", {"param": "value"})

            mock_psql.execute_sql.assert_called_once_with("SELECT * FROM users", {"param": "value"})
            assert len(result) == 1
            assert isinstance(result[0], db.Row)

    @pytest.mark.asyncio
    async def test_shutdown_postgres(self):
        """Test shutdown with PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            mock_psql.shutdown = AsyncMock()
            db._db_module = DBModule.POSTGRES

            await db.shutdown()
            mock_psql.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_sqlite(self):
        """Test shutdown with SQLite (no-op)"""
        db._db_module = DBModule.SQLITE
        # Should not raise any error
        await db.shutdown()

    def test_transaction_postgres(self):
        """Test transaction with PostgreSQL"""
        with patch("jubtools.db._psql") as mock_psql:
            mock_req = Mock()
            mock_transaction = Mock()
            mock_psql.transaction = Mock(return_value=mock_transaction)
            db._db_module = DBModule.POSTGRES

            result = db.transaction(mock_req)

            mock_psql.transaction.assert_called_once_with(mock_req)
            assert result == mock_transaction

    def test_transaction_sqlite_not_implemented(self):
        """Test transaction with SQLite (not implemented)"""
        db._db_module = DBModule.SQLITE
        mock_req = Mock()

        with pytest.raises(db.DatabaseError, match="SQLite transaction function not implemented"):
            db.transaction(mock_req)
