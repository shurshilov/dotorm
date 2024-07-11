import asyncpg
from asyncpg.transaction import Transaction

from ..types import PoolSettings

from ...exceptions import (
    PostgresConnectionExecuteException,
    PostgresGetConnectionExecuteException,
    PostgresQueryExecuteException,
)
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
        try:

            # Заменить %s на $1...$n dollar-numberic
            counter = 1
            while "%s" in stmt:
                stmt = stmt.replace("%s", "$" + str(counter), 1)
                counter += 1
            # if func_cur == "lastrowid":
            #     func_cur = "fetchrow"

            rows_dict = []
            if not func_cur:
                if val:
                    rows = await self.connection.execute(stmt, *val)
                else:
                    rows = await self.connection.execute(stmt)
            # elif func_cur == "lastrowid":
            # rows = await self.connection.execute(stmt, *val)
            # rows = await self.connection.execute(
            #     "SELECT currval('persons_id_seq');"
            # )
            # rows = await self.connection.execute(stmt, *val)
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

        except (ConnectionError, TimeoutError) as exc:
            raise PostgresConnectionExecuteException(stmt) from exc
        except Exception as exc:
            raise PostgresQueryExecuteException(stmt) from exc

    async def fetch(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
    ):
        try:
            if val:
                rows = await self.connection.fetch(stmt, val)
            else:
                rows = await self.connection.fetch(stmt)

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
        try:
            conn = await cls.get_connection(**settings)

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
    async def get_connection(cls, settings: PoolSettings):
        try:
            conn: asyncpg.Connection = await asyncpg.connect(**settings)
            assert isinstance(conn, asyncpg.Connection)
            return conn
        except Exception as exc:
            raise PostgresGetConnectionExecuteException(
                "Error create connection"
            ) from exc
