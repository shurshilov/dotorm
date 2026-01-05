import aiomysql

from ..abstract.session import SessionAbstract


class MysqlSession(SessionAbstract): ...


class TransactionSession(MysqlSession):
    """тот класс работает в одном соединении не закрывая его.
    Пока его не закроют явно. Используется при работе в транзакции.
    Паттерн unit of work."""

    def __init__(
        self, connection: aiomysql.Connection, cursor: aiomysql.Cursor
    ) -> None:
        self.connection = connection
        self.cursor = cursor

    async def execute(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur=None,
    ):
        if val:
            await self.cursor.execute(stmt, val)
        else:
            await self.cursor.execute(stmt)

        if func_cur == "lastrowid":
            rows = self.cursor.lastrowid
        elif func_cur is not None:
            rows = await getattr(self.cursor, func_cur)()

        if func_prepare:
            return func_prepare(rows)
        return rows


class NoTransactionSession(MysqlSession):
    "Этот класс берет соединение из пулла и выполняет запросв нем."

    # если не передан пул, то тогда будет взят пул заданый по умолчанию в классе
    default_pool: aiomysql.Pool | None = None

    def __init__(self, pool: aiomysql.Pool | None = None) -> None:
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def execute(
        self, stmt: str, val=None, func_prepare=None, func_cur="fetchall"
    ):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if val:
                    await cur.execute(stmt, val)
                else:
                    await cur.execute(stmt)
                # если режим автокомита False
                if func_cur == "lastrowid":
                    rows = cur.lastrowid
                else:
                    rows = await getattr(cur, func_cur)()
                # если режим автокомита False
                if func_prepare:
                    return func_prepare(rows)
        return rows
