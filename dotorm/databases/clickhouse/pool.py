import logging
import asyncio
import asynch
import time

from ..types import ClickhousePoolSettings

log = logging.getLogger("dotorm")


class ClickhousePool:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    # РАБОТА С ПУЛОМ
    async def connect(self, settings: ClickhousePoolSettings):
        try:
            start_time: float = time.time()
            pool = await asynch.create_pool(
                **settings,
                min_size=5,
                max_size=15,
                # command_timeout=60,
                # 15 minutes
                # max_inactive_connection_lifetime
                # pool_recycle=60 * 15,
            )
            # assert isinstance(pool, asyncpg.Pool)
            assert pool is not None
            self.pool = pool
            start_time: float = time.time()

            log.debug(
                "Connection Clickhouse db: %s, created time: [%0.3fs]",
                settings["database"],
                time.time() - start_time,
            )
            return self.pool
        except (ConnectionError, TimeoutError) as e:
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Clickhouse create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(10)
            await self.connect(settings)
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Clickhouse create pool error:")
            raise e


clickhouse_pool = ClickhousePool()
