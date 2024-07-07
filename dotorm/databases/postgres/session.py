import asyncpg
from asyncpg.transaction import Transaction

from dotorm.exceptions import (
    PostgresConnectionExecuteException,
    PostgresGetConnectionExecuteException,
    PostgresQueryExecuteException,
)


class PostgresSessionWithTransactionSingleConnection:
    """Этот класс работает в одном соединении не закрывая его.
    Пока его не закроют явно. Используется при работе в транзакции.
    Паттерн unit of work."""

    def __init__(
        self, connection: asyncpg.Connection, transaction: Transaction
    ) -> None:
        self.connection = connection
        self.transaction = transaction

    async def execute(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="fetch",
    ):
        try:
            if val:
                await self.connection.execute(stmt, val)
            else:
                await self.connection.execute(stmt)

                rows = await getattr(self.connection, func_cur)()

            if func_prepare:
                return func_prepare(rows)
            return rows

        except (ConnectionError, TimeoutError) as exc:
            raise PostgresConnectionExecuteException(stmt) from exc
        except Exception as exc:
            raise PostgresQueryExecuteException(stmt) from exc


# class PostgresSessionWithPool:
#     "Этот класс берет соединение из пулла и выполняет запросв нем."

#     @classmethod
#     async def execute(cls, stmt: str, val=None, func_prepare=None, func_cur="fetchall"):
#         try:
#             async with pg_pool.pool_no_auto_commit.acquire() as conn:
#                 async with conn.cursor(asyncpg.DictCursor) as cur:
#                     if val:
#                         await cur.execute(stmt, val)
#                     else:
#                         await cur.execute(stmt)
#                     if func_cur == "lastrowid":
#                         rows = cur.lastrowid
#                     else:
#                         rows = await getattr(cur, func_cur)()
#                     if func_prepare:
#                         return func_prepare(rows)
#                     return rows
#         except (ConnectionError, TimeoutError) as e:
#             raise PostgresConnectionExecuteException(stmt) from e
#         except Exception as e:
#             raise PostgresQueryExecuteException(stmt) from e


class PostgresSessionWithoutTransaction:
    """Этот класс открывает одиночное соединение (не используя пулл)
    и после выполнения сразу закрывает его."""

    @classmethod
    async def execute(
        cls,
        settings,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="fetch",
        # fetchrow
    ):
        try:
            conn: asyncpg.Connection = await cls.get_connection(**settings)
            assert isinstance(conn, asyncpg.Connection)

            if val:
                await conn.execute(stmt, val)
            else:
                await conn.execute(stmt)
            # if func_cur == "lastrowid":
            #     rows = conn.lastrowid
            # else:
            rows = await getattr(conn, func_cur)()
            await conn.close()
            if func_prepare:
                return func_prepare(rows)
            return rows

        except (ConnectionError, TimeoutError) as e:
            raise PostgresConnectionExecuteException(stmt) from e
        except Exception as e:
            raise PostgresQueryExecuteException(stmt) from e

    @classmethod
    async def get_connection(cls, settings):
        try:
            conn = await asyncpg.connect(**settings)
            return conn
        except Exception as exc:
            raise PostgresGetConnectionExecuteException(
                "Error create connection"
            ) from exc
