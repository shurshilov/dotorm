"""PostgreSQL transaction management."""

try:
    import asyncpg
    from asyncpg.transaction import Transaction
except ImportError:
    asyncpg = None  # type: ignore
    Transaction = None  # type: ignore

from .session import TransactionSession


class ContainerTransaction:
    """
    Transaction context manager for PostgreSQL.

    Acquires connection, starts transaction, executes queries,
    commits on success, rollbacks on exception.

    Example:
        async with ContainerTransaction(pool) as session:
            await session.execute("INSERT INTO users ...")
            await session.execute("INSERT INTO orders ...")
            # Commits on exit
    """

    default_pool: "asyncpg.Pool | None" = None

    def __init__(self, pool: "asyncpg.Pool | None" = None):
        self.session_factory = TransactionSession
        if pool is None:
            assert self.default_pool is not None
            self.pool = self.default_pool
        else:
            self.pool = pool

    async def __aenter__(self):
        connection: "asyncpg.Connection" = await self.pool.acquire()
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
