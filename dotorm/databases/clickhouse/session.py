import asynch


from ..sesson_abstract import SessionAbstract


class ClickhouseSessionWithPool(SessionAbstract):
    "Этот класс берет соединение из пулла и выполняет запросв нем."

    def __init__(self, pool: asynch.pool.Pool) -> None:
        self.pool = pool

    async def execute(
        self, stmt: str, val=None, func_prepare=None, func_cur="fetchall"
    ):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if val:
                    await cursor.execute(stmt, val)
                else:
                    await cursor.execute(stmt)
                rows = await cursor.fetchall()
                if func_prepare and rows:
                    return func_prepare(rows)
                return rows
