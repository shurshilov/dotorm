import aiomysql

from .session import TransactionSession


class ContainerTransaction:
    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def __aenter__(self):
        connection: aiomysql.Connection = await self.pool._acquire()
        cursor: aiomysql.Cursor = await connection.cursor(aiomysql.DictCursor)
        self.session = TransactionSession(connection, cursor)

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.connection.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.connection.commit()
        await self.session.cursor.close()
        # В любом случае закрыть соединение и курсор
        await self.pool.release(self.session.connection)
