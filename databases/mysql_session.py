import aiomysql
from .mysql_pool import mysqlPoolObject

from exceptions import (
    MysqlConnectionExecuteException,
    MysqlQueryExecuteException,
)


class MysqlSessionWithTransactionSingleConnection:
    "Выполнить из коннекшена который уже есть"

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
        func_cur="fetchall",
        db=None,
        autocommit=False,
    ):
        try:
            if val:
                await self.cursor.execute(stmt, val)
            else:
                await self.cursor.execute(stmt)

            if func_cur == "lastrowid":
                rows = self.cursor.lastrowid
            else:
                rows = await getattr(self.cursor, func_cur)()

            if func_prepare:
                return func_prepare(rows)
            return rows

        except (ConnectionError, TimeoutError) as e:
            raise MysqlConnectionExecuteException(stmt) from e
        except Exception as e:
            raise MysqlQueryExecuteException(stmt) from e


class MysqlSessionWithPool:
    "Выполнить из коннекшена который взят из пула"

    @classmethod
    async def execute(
        cls,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="fetchall",
        db=None,
        autocommit=None,
    ):
        try:
            async with mysqlPoolObject.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    if val:
                        await cur.execute(stmt, val)
                    else:
                        await cur.execute(stmt)
                    if func_cur == "lastrowid":
                        rows = cur.lastrowid
                    else:
                        rows = await getattr(cur, func_cur)()
                    if func_prepare:
                        return func_prepare(rows)
                    return rows
        except (ConnectionError, TimeoutError) as e:
            raise MysqlConnectionExecuteException(stmt) from e
        except Exception as e:
            raise MysqlQueryExecuteException(stmt) from e
