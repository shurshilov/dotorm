from typing import Any, Callable

try:
    import asynch
except ImportError:
    ...

from ..abstract.session import SessionAbstract


class ClickhouseSession(SessionAbstract): ...


class NoTransactionSession(ClickhouseSession):
    """Этот класс берет соединение из пулла и выполняет запрос в нем."""

    def __init__(self, pool: asynch.Pool):
        self.pool = pool

    async def execute(
        self,
        stmt: str,
        values: Any = None,
        *,
        prepare: Callable | None = None,
        cursor: str = "fetchall",
    ) -> Any:
        """
        Простая реализация сессии в кликхаусе.
        Выполнение запроса, и возврат соединения в пул.
        """

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                assert isinstance(cur, asynch.Cursor)
                if values:
                    await cur.execute(stmt, values)
                else:
                    await cur.execute(stmt)
                rows = await cur.fetchall()
                if prepare and rows:
                    return prepare(rows)
                return rows
