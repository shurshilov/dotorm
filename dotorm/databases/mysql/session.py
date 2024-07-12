import aiomysql


from ..sesson_abstract import SessionAbstract


class MysqlSessionWithPoolTransaction(SessionAbstract):
    """тот класс работает в одном соединении не закрывая его.
    Пока его не закроют явно. Используется при работе в транзакции.
    Паттерн unit of work."""

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
        func_cur=None,
    ):
        if val:
            await self.cursor.execute(stmt, val)
        else:
            await self.cursor.execute(stmt)

        if func_cur == "lastrowid":
            rows = self.cursor.lastrowid
        elif func_cur is not None:
            rows = await getattr(self.cursor, func_cur)()

        if func_prepare:
            return func_prepare(rows)
        return rows


class MysqlSessionWithPool(SessionAbstract):
    "Этот класс берет соединение из пулла и выполняет запросв нем."

    def __init__(self, pool: aiomysql.Pool) -> None:
        self.pool = pool

    async def execute(
        self, stmt: str, val=None, func_prepare=None, func_cur="fetchall"
    ):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if val:
                    await cur.execute(stmt, val)
                else:
                    await cur.execute(stmt)
                # если режим автокомита False
                # await conn.commit()
                if func_cur == "lastrowid":
                    rows = cur.lastrowid
                else:
                    rows = await getattr(cur, func_cur)()
                # если режим автокомита False
                # await conn.commit()
                if func_prepare:
                    return func_prepare(rows)
        return rows


# class MysqlSession(SessionAbstract):
#     """Этот класс открывает одиночное соединение (не используя пулл)
#     и после выполнения сразу закрывает его."""

#     @classmethod
#     async def execute(
#         cls,
#         settings,
#         stmt: str,
#         val=None,
#         func_prepare=None,
#         func_cur="fetchall",
#         db=None,
#         autocommit=None,
#     ):
#         try:
#             conn: aiomysql.Connection = await cls.get_connection(
#                 settings, db=db, autocommit=autocommit
#             )
#             cur: aiomysql.Cursor = await conn.cursor(aiomysql.DictCursor)
#             if val:
#                 await cur.execute(stmt, val)
#             else:
#                 await cur.execute(stmt)
#             if func_cur == "lastrowid":
#                 rows = cur.lastrowid
#             else:
#                 rows = await getattr(cur, func_cur)()
#             # await cur.commit()
#             await cur.close()
#             conn.close()
#             if func_prepare:
#                 return func_prepare(rows)
#             return rows
#         except (ConnectionError, TimeoutError) as e:
#             raise MysqlConnectionExecuteException(stmt) from e
#         except Exception as e:
#             raise MysqlQueryExecuteException(stmt) from e

#     @classmethod
#     async def get_connection(cls, settings, db=None, autocommit=None):
#         try:
#             conn = await aiomysql.connect(
#                 host=settings.db_portal_host if not db else settings.db_cl_host,
#                 port=settings.db_portal_port if not db else settings.db_cl_port,
#                 user=settings.db_portal_user if not db else settings.db_cl_user,
#                 password=(
#                     settings.db_portal_password if not db else settings.db_cl_password
#                 ),
#                 db=settings.db_portal_database if not db else settings.db_cl_database,
#                 autocommit=True if not db else False,
#                 # autocommit=autocommit,
#             )

#             return conn
#         except Exception as e:
#             raise MysqlGetConnectionExecuteException("Get connection") from e
