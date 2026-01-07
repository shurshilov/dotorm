"""MySQL session implementations."""

from typing import Any, Callable

try:
    import aiomysql
except ImportError:
    ...

from ..abstract.session import SessionAbstract


class MysqlSession(SessionAbstract): ...


class TransactionSession(MysqlSession):
    """Этот класс работает в одном соединении не закрывая его.
    Пока его не закроют явно. Используется при работе в транзакции.
    Паттерн unit of work."""

    def __init__(
        self, connection: "aiomysql.Connection", cursor: "aiomysql.Cursor"
    ) -> None:
        self.connection = connection
        self.cursor = cursor

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "fetchall",
    ) -> Any:
        if values:
            await self.cursor.execute(stmt, values)
        else:
            await self.cursor.execute(stmt)

        if cursor == "lastrowid":
            rows = self.cursor.lastrowid
        elif cursor is not None:
            rows = await getattr(self.cursor, cursor)()
        else:
            rows = None

        if prepare:
            return prepare(rows)
        return rows


class NoTransactionSession(MysqlSession):
    """
    Session for non-transactional queries.

    Uses pool with autocommit enabled.
    """

    default_pool: "aiomysql.Pool | None" = None

    def __init__(self, pool: "aiomysql.Pool | None" = None) -> None:
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
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if values:
                    await cur.execute(stmt, values)
                else:
                    await cur.execute(stmt)

                if cursor == "lastrowid":
                    rows = cur.lastrowid
                else:
                    rows = await getattr(cur, cursor)()

                if prepare:
                    return prepare(rows)
        return rows
