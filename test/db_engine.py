"""
Genesis QA - Database Test Engine
==================================
Tests database connections, query execution, and schema validation.
This engine is optional — it only runs when database connection
configuration is provided.

Usage:
    engine = DbEngine("postgresql://user:pass@localhost/db")
    result = engine.test_connection()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from test.base_engine import BaseEngine, TestResult, ScenarioConfig

logger = logging.getLogger(__name__)

# Try to import database drivers — failure just means the engine is
# unavailable, not that the whole test run should break.
try:
    import sqlalchemy
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    sqlalchemy = None  # type: ignore[assignment]
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    SQLAlchemyError = Exception  # type: ignore[assignment,misc]


class DbEngine(BaseEngine):
    """Engine for testing database connectivity and schema.

    Note:
        This engine requires **SQLAlchemy** and a compatible database driver
        (e.g. psycopg2 for PostgreSQL, pymysql for MySQL). If SQLAlchemy is
        not installed, all tests will return a ``TestResult`` with
        ``passed=False`` and an explanatory error message.

    Attributes:
        connection_string: SQLAlchemy connection URL.
        engine:            SQLAlchemy ``Engine`` instance (if available).
    """

    def __init__(
        self,
        connection_string: str,
        *,
        timeout: float = 30.0,
        schema_tables: Optional[list[str]] = None,
    ) -> None:
        """Initialize the database engine.

        Args:
            connection_string: SQLAlchemy connection URL (e.g.
                               ``postgresql://user:pass@host/db``).
            timeout:           Query timeout in seconds.
            schema_tables:     Optional list of table names to validate exist.
        """
        # DbEngine doesn't use base_url in the traditional sense;
        # we pass the connection string as base_url for consistency.
        super().__init__(connection_string, timeout=timeout)
        self.connection_string = connection_string
        self.schema_tables = schema_tables or []
        self._engine: Any = None

        if HAS_SQLALCHEMY:
            try:
                self._engine = create_engine(
                    connection_string,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args={"connect_timeout": timeout},
                )
                logger.debug(
                    "DbEngine: SQLAlchemy engine created for %s",
                    connection_string.split("@")[-1] if "@" in connection_string else "unknown",
                )
            except Exception as exc:
                logger.warning("DbEngine: Failed to create SQLAlchemy engine: %s", exc)

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Run a DB test scenario."""
        name_lower = scenario.name.lower()
        if "connect" in name_lower:
            return self.test_connection()
        elif "query" in name_lower:
            query = (
                scenario.body.get("query", "SELECT 1") if scenario.body else "SELECT 1"
            )
            return self.test_query(query)
        elif "schema" in name_lower or "table" in name_lower:
            return self.test_schema_validation()
        else:
            return self.test_connection()

    def test_connection(self) -> TestResult:
        """Test the database connection.

        Returns:
            A ``TestResult`` indicating whether the connection succeeded.
        """
        if not HAS_SQLALCHEMY:
            return TestResult(
                name="Database Connection",
                passed=False,
                error="SQLAlchemy is not installed. Run: pip install sqlalchemy",
                endpoint=self.connection_string,
                method="N/A",
                details={"available": False},
            )

        if self._engine is None:
            return TestResult(
                name="Database Connection",
                passed=False,
                error="Failed to create SQLAlchemy engine",
                endpoint=self.connection_string,
                method="N/A",
                details={"available": True, "engine_created": False},
            )

        start = __import__("time").monotonic()
        error = ""
        db_version = ""

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT VERSION()"))
                row = result.fetchone()
                if row:
                    db_version = str(row[0])
                conn.commit()
        except SQLAlchemyError as exc:
            error = f"Connection failed: {exc}"
        except Exception as exc:
            error = f"Unexpected error: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error

        result = TestResult(
            name="Database Connection",
            passed=passed,
            status_code=200 if passed else 0,
            expected_status=[200],
            endpoint=self.connection_string,
            method="SQL",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview="",
            details={
                "db_version": db_version,
                "dialect": self.connection_string.split("://")[0] if "://" in self.connection_string else "unknown",
                "available": True,
                "engine_created": True,
            },
        )

        self._log_result(result)
        return result

    def test_query(self, query: str = "SELECT 1") -> TestResult:
        """Execute a SQL query and return the result.

        Args:
            query: SQL query string to execute.

        Returns:
            A ``TestResult``.
        """
        if self._engine is None:
            return TestResult(
                name=f"Query: {query[:50]}",
                passed=False,
                error="Database engine not available",
                method="SQL",
                details={"available": False},
            )

        start = __import__("time").monotonic()
        error = ""
        row_count = 0
        columns: list[str] = []

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(query))
                columns = list(result.keys()) if result.returns_rows else []
                rows = result.fetchmany(10) if result.returns_rows else []
                row_count = len(rows) if result.returns_rows else -1
                conn.commit()
        except SQLAlchemyError as exc:
            error = f"Query failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error

        result = TestResult(
            name=f"Query: {query[:50]}",
            passed=passed,
            status_code=200 if passed else 0,
            expected_status=[200],
            method="SQL",
            timing_ms=elapsed_ms,
            error=error,
            details={
                "query": query[:200],
                "columns": columns,
                "row_count": row_count,
            },
        )

        self._log_result(result)
        return result

    def test_schema_validation(self) -> TestResult:
        """Validate that expected tables exist in the database.

        Returns:
            A ``TestResult``.
        """
        if self._engine is None:
            return TestResult(
                name="Schema Validation",
                passed=False,
                error="Database engine not available",
                method="SQL",
                details={"available": False},
            )

        if not self.schema_tables:
            # Auto-detect: try to list tables
            return self._list_tables()

        start = __import__("time").monotonic()
        error = ""
        existing_tables: list[str] = []
        missing_tables: list[str] = []

        try:
            from sqlalchemy import inspect

            with self._engine.connect() as conn:
                inspector = inspect(conn)
                existing_tables = inspector.get_table_names()
        except SQLAlchemyError as exc:
            error = f"Schema inspection failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)

        if not error:
            missing_tables = [
                t for t in self.schema_tables if t not in existing_tables
            ]
            if missing_tables:
                error = f"Missing tables: {missing_tables}"

        passed = not error

        result = TestResult(
            name="Schema Validation",
            passed=passed,
            status_code=200 if passed else 0,
            expected_status=[200],
            method="SQL",
            timing_ms=elapsed_ms,
            error=error,
            details={
                "expected_tables": self.schema_tables,
                "existing_tables": existing_tables,
                "missing_tables": missing_tables,
                "table_count": len(existing_tables),
            },
        )

        self._log_result(result)
        return result

    def _list_tables(self) -> TestResult:
        """List all tables in the database (auto-discovery mode)."""
        try:
            from sqlalchemy import inspect

            with self._engine.connect() as conn:  # type: ignore[union-attr]
                inspector = inspect(conn)
                table_names = inspector.get_table_names()
        except Exception as exc:
            return TestResult(
                name="Schema Discovery",
                passed=False,
                error=f"Cannot list tables: {exc}",
                method="SQL",
                details={"available": True, "error": str(exc)},
            )

        return TestResult(
            name="Schema Discovery",
            passed=True,
            status_code=200,
            expected_status=[200],
            method="SQL",
            error="",
            details={
                "tables": table_names,
                "table_count": len(table_names),
            },
        )
