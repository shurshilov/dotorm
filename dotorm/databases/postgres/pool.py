import logging
import asyncio
import asyncpg
import time

from backend.dotorm.dotorm.databases.types import PoolSettings

log = logging.getLogger("dotorm")


class Pool:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    # РАБОТА С ПУЛОМ
    async def connect(self, settings: PoolSettings):
        try:
            start_time: float = time.time()
            pool = await asyncpg.create_pool(
                **settings,
                min_size=5,
                # max_size=15,
                command_timeout=60,
                # autocommit=False,
                # 15 minutes
                # max_inactive_connection_lifetime
                # pool_recycle=60 * 15,
            )
            assert pool is not None
            self.pool_auto_commit = pool
            start_time: float = time.time()

            log.debug(
                "Connection PostgreSQL db: %s, created time: [%0.3fs]",
                settings["database"],
                time.time() - start_time,
            )
            return self
        except (
            ConnectionError,
            TimeoutError,
            asyncpg.exceptions.ConnectionFailureError,
        ) as e:
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Postgres create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(10)
            await self.connect(settings)
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Postgres create pool error:")
            raise e


pg_pool = Pool()
