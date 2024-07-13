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

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def execute(
        self, stmt: str, val=None, func_prepare=None, func_cur="fetchall"
    ):
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
                if val:
                    rows = await conn.fetch(stmt, *val)
                else:
                    rows = await conn.fetch(stmt)
                for rec in rows:
                    rows_dict.append(dict(rec))

            if func_prepare:
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
