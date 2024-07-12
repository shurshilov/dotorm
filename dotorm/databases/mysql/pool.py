import aiomysql
import asyncio
import logging
import time

from ..types import MysqlPoolSettings

log = logging.getLogger("dotorm")


class MysqlPool:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    # РАБОТА С ПУЛОМ
    async def mysql_connect(self, settings: MysqlPoolSettings):
        try:
            start_time: float = time.time()
            self.pool: aiomysql.Pool = await aiomysql.create_pool(
                **settings,
                minsize=5,
                # maxsize=15,
                autocommit=True,
                # 15 minutes
                pool_recycle=60 * 15,
            )
            start_time: float = time.time()
            log.debug(
                "Connection MySQL db: %s, created time: [%0.3fs]",
                settings["db"],
                time.time() - start_time,
            )
            return self.pool
        except (ConnectionError, TimeoutError, aiomysql.OperationalError) as e:
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Mysql create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(10)
            await self.mysql_connect(settings)
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Mysql create poll error:")
            raise e


mysql_pool = MysqlPool()
