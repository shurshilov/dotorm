import asyncpg
from asyncpg.transaction import Transaction

from .pool import pg_pool
from .session import PostgresSessionWithTransactionSingleConnection


class TransactionPostgresDotORM:
    def __init__(self, connection=None):
        self.session_factory = PostgresSessionWithTransactionSingleConnection
        self.connection = connection

    async def __aenter__(self):
        if self.connection:
            connection = self.connection
        else:
            connection: asyncpg.Connection = await pg_pool.pool_auto_commit.acquire()

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
        if self.connection:
            await self.connection.close()
        else:
            # В любом случае вернуть соединение в пул
            await pg_pool.pool_auto_commit.release(self.session.connection)
