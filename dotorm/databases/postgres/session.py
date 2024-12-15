import asyncpg
from asyncpg.transaction import Transaction

from ..types import PostgresPoolSettings
from ..sesson_abstract import SessionAbstract


class PostgresSessionWithTransactionSingleConnection(SessionAbstract):
    """Этот класс работает в одном соединении не закрывая его.
    Пока его не закроют явно. Используется при работе в транзакции.
    Паттерн unit of work."""

    def __init__(
        self, connection: asyncpg.Connection, transaction: Transaction
    ) -> None:
        self.connection = connection
        self.transaction = transaction

    async def execute(self, stmt: str, val=[], func_prepare=None, func_cur=None):
        # Заменить %s на $1...$n dollar-numberic
        counter = 1
        while "%s" in stmt:
            stmt = stmt.replace("%s", "$" + str(counter), 1)
            counter += 1

        rows_dict = []
        if not func_cur:
            if val:
                rows = await self.connection.execute(stmt, *val)
            else:
                rows = await self.connection.execute(stmt)
        else:
            if val:
                rows = await self.connection.fetch(stmt, *val)
            else:
                rows = await self.connection.fetch(stmt)
            for rec in rows:
                rows_dict.append(dict(rec))

        if func_prepare:
            return func_prepare(rows_dict)
        return rows_dict or rows

    async def fetch(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
    ):
        if val:
            rows = await self.connection.fetch(stmt, val)
        else:
            rows = await self.connection.fetch(stmt)

        if func_prepare:
            return func_prepare(rows)
        return rows


class PostgresSessionWithPool(SessionAbstract):
    "Этот класс берет соединение из пулла и выполняет запросв нем."

    # если не передан пул, то тогда будет взят пул заданый по умолчанию в классе
    default_pool: asyncpg.Pool | None = None

    def __init__(self, pool: asyncpg.Pool | None = None) -> None:
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def execute(self, stmt: str, val=None, func_prepare=None, func_cur="fetch"):
        async with self.pool.acquire() as conn:
            # Заменить %s на $1...$n dollar-numberic
            counter = 1
            while "%s" in stmt:
                stmt = stmt.replace("%s", "$" + str(counter), 1)
                counter += 1

            rows_dict = []
            if not func_cur:
                if val:
                    rows = await conn.execute(stmt, *val)
                else:
                    rows = await conn.execute(stmt)
            else:
                # TODO: удалить явную поддержку posgres
                if func_cur == "fetchall":
                    func_cur = "fetch"
                if val:
                    rows = await getattr(conn, func_cur)(stmt, *val)
                    # rows = await conn.fetch(stmt, *val)
                else:
                    rows = await getattr(conn, func_cur)(stmt)
                    # rows = await conn.fetch(stmt)
                if rows:
                    for rec in rows:
                        rows_dict.append(dict(rec))

            if func_prepare and rows_dict:
                return func_prepare(rows_dict)
            return rows_dict or rows


class PostgresSessionWithoutTransaction(SessionAbstract):
    """Этот класс открывает одиночное соединение (не используя пулл)
    и после выполнения сразу закрывает его."""

    @classmethod
    async def execute(
        cls,
        settings,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="execute",
        # fetchrow, fetch
    ):
        conn = await cls.get_connection(**settings)

        if val:
            await conn.execute(stmt, val)
        else:
            await conn.execute(stmt)

        rows = await getattr(conn, func_cur)()
        await conn.close()
        if func_prepare:
            return func_prepare(rows)
        return rows

    @classmethod
    async def get_connection(cls, settings: PostgresPoolSettings):
        conn: asyncpg.Connection = await asyncpg.connect(**settings)
        assert isinstance(conn, asyncpg.Connection)
        return conn
