import aiomysql

from .session import MysqlSessionWithPoolTransaction


class TransactionMysqlDotORM:
    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool
        # self._opened = False

    async def __aenter__(self):
        connection: aiomysql.Connection = await self.pool._acquire()
        cursor: aiomysql.Cursor = await connection.cursor(aiomysql.DictCursor)
        self.session = MysqlSessionWithPoolTransaction(connection, cursor)
        # self._opened = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # try:
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.connection.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.connection.commit()
        await self.session.cursor.close()
        # В любом случае закрыть соединение и курсор
        await self.pool.release(self.session.connection)


# class NoTransactionMysqlDotORM:
#     def __init__(self, pool: aiomysql.Pool):
#         self.pool = pool
#         # self._opened = False

#     async def __aenter__(self):
#         self.session = MysqlSessionWithPool(self.pool)
#         # self._opened = True

#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         self.session = None
