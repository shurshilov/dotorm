import asynch

from ..abstract.session import SessionAbstract


class ClickhouseSession(SessionAbstract): ...


class NoTransactionSession(ClickhouseSession):
    "Этот класс берет соединение из пулла и выполняет запрос в нем."

    def __init__(self, pool: asynch.Pool):
        self.pool = pool

    async def execute(self, stmt: str, val=None, func_prepare=None):
        """
        Простая реализация сессии в кликхаусе.
        Выполнение запроса, и возврат соединения в пул.
        """

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                assert isinstance(cursor, asynch.Cursor)
                if val:
                    await cursor.execute(stmt, val)
                else:
                    await cursor.execute(stmt)
                rows = await cursor.fetchall()
                if func_prepare and rows:
                    return func_prepare(rows)
                return rows
