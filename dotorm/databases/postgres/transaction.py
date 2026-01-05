import asyncpg
from asyncpg.transaction import Transaction

from .session import TransactionSession


class ContainerTransaction:
    # если не передан пул, то тогда будет взят пул заданый по умолчанию в классе
    default_pool: asyncpg.Pool | None = None

    def __init__(self, pool: asyncpg.Pool | None = None):
        self.session_factory = TransactionSession
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def __aenter__(self):
        connection: asyncpg.Connection = await self.pool.acquire()

        transaction = connection.transaction()

        assert isinstance(transaction, Transaction)
        assert isinstance(connection, asyncpg.Connection)

        await transaction.start()
        self.session = self.session_factory(connection, transaction)

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.transaction.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.transaction.commit()
        # В любом случае вернуть соединение в пул
        await self.pool.release(self.session.connection)
