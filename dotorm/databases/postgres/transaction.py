import asyncpg
from asyncpg.transaction import Transaction

from .session import PostgresSessionWithTransactionSingleConnection


class TransactionPostgresDotORM:
    def __init__(self, pool: asyncpg.Pool):
        self.session_factory = PostgresSessionWithTransactionSingleConnection
        self.pool = pool

    async def __aenter__(self):
        connection: asyncpg.Connection = await self.pool.acquire()

        transaction = connection.transaction()

        assert isinstance(transaction, Transaction)
        assert isinstance(connection, asyncpg.Connection)

        await transaction.start()
        self.session = self.session_factory(connection, transaction)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.transaction.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.transaction.commit()
        # В любом случае вернуть соединение в пул
        await self.pool.release(self.session.connection)
