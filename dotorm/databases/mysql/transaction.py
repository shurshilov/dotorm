import aiomysql

from .pool import mysql_pool
from .session import MysqlSessionWithTransactionSingleConnection


class TransactionMysqlDotORM:
    def __init__(self):
        self.session_factory = MysqlSessionWithTransactionSingleConnection

    async def __aenter__(self):
        connection: aiomysql.Connection = (
            await mysql_pool.mysql_pool_no_auto_commit._acquire()
        )
        cursor: aiomysql.Cursor = await connection.cursor(aiomysql.DictCursor)
        self.session = self.session_factory(connection, cursor)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Выпало исключение вызвать ролбек
            await self.session.connection.rollback()
        else:
            # Не выпало исключение вызвать комит
            await self.session.connection.commit()
        await self.session.cursor.close()
        # self.session.conn.close()
        # В любом случае закрыть соединение и курсор
        await mysql_pool.mysql_pool_no_auto_commit.release(self.session.connection)
