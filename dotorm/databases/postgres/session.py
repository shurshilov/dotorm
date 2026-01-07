"""PostgreSQL session implementations."""

from typing import Any, Callable

from ..abstract.types import PostgresPoolSettings
from ..abstract.session import SessionAbstract


try:
    import asyncpg
    from asyncpg.transaction import Transaction
except ImportError:
    asyncpg = None  # type: ignore
    Transaction = None  # type: ignore


class PostgresSession(SessionAbstract): ...


class TransactionSession(PostgresSession):
    """
    Session for transactional queries.

    Works in single connection without closing it.
    Used in transaction context manager.
    """

    def __init__(
        self, connection: "asyncpg.Connection", transaction: "Transaction"
    ) -> None:
        self.connection = connection
        self.transaction = transaction

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "fetchall",
    ) -> Any:
        # Заменить %s на $1...$n dollar-numberic
        counter = 1
        while "%s" in stmt:
            stmt = stmt.replace("%s", "$" + str(counter), 1)
            counter += 1

        rows_dict = []
        if cursor is None:
            if values:
                rows = await self.connection.execute(stmt, *values)
            else:
                rows = await self.connection.execute(stmt)
        else:
            if values:
                rows = await self.connection.fetch(stmt, *values)
            else:
                rows = await self.connection.fetch(stmt)
            for rec in rows:
                rows_dict.append(dict(rec))

        if prepare:
            return prepare(rows_dict)
        return rows_dict or rows

    async def fetch(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
    ) -> Any:
        if values:
            rows = await self.connection.fetch(stmt, values)
        else:
            rows = await self.connection.fetch(stmt)

        if prepare:
            return prepare(rows)
        return rows


class NoTransactionSession(PostgresSession):
    """
    Session for non-transactional queries.

    Acquires connection from pool, executes query, releases back to pool.
    """

    default_pool: "asyncpg.Pool | None" = None

    def __init__(self, pool: "asyncpg.Pool | None" = None) -> None:
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "fetchall",
    ) -> Any:
        async with self.pool.acquire() as conn:
            # Заменить %s на $1...$n dollar-numberic
            counter = 1
            while "%s" in stmt:
                stmt = stmt.replace("%s", "$" + str(counter), 1)
                counter += 1

            rows_dict = []
            if cursor is None:
                if values:
                    rows = await conn.execute(stmt, *values)
                else:
                    rows = await conn.execute(stmt)
            else:
                # asyncpg использует fetch вместо fetchall
                cursor_method = "fetch" if cursor == "fetchall" else cursor
                if values:
                    rows = await getattr(conn, cursor_method)(stmt, *values)
                else:
                    rows = await getattr(conn, cursor_method)(stmt)
                if rows:
                    for rec in rows:
                        rows_dict.append(dict(rec))

            if prepare and rows_dict:
                return prepare(rows_dict)
            return rows_dict or rows


class NoTransactionNoPoolSession(PostgresSession):
    """
    Session without pool.

    Opens single connection, executes query, closes connection.
    Used for administrative tasks like creating databases.
    """

    @classmethod
    async def execute(
        cls,
        settings,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "execute",
    ) -> Any:
        conn = await cls.get_connection(settings)

        if values:
            await conn.execute(stmt, values)
        else:
            await conn.execute(stmt)

        rows = await getattr(conn, cursor)()
        await conn.close()
        if prepare:
            return prepare(rows)
        return rows

    @classmethod
    async def get_connection(cls, settings: PostgresPoolSettings):
        conn: "asyncpg.Connection" = await asyncpg.connect(
            **settings.model_dump()
        )
        return conn
