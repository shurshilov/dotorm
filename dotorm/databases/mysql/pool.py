import aiomysql
import asyncio
import logging
import time

from ..abstract.types import ContainerSettings, MysqlPoolSettings


log = logging.getLogger(__package__)


class ContainerMysql:
    def __init__(
        self,
        pool_settings: MysqlPoolSettings,
        container_settings: ContainerSettings,
    ):
        self.pool_settings = pool_settings
        self.container_settings = container_settings

    # РАБОТА С ПУЛОМ
    async def create_pool(self):
        try:
            start_time: float = time.time()
            self.pool: aiomysql.Pool = await aiomysql.create_pool(
                **self.pool_settings.model_dump(),
                minsize=5,
                maxsize=15,
                autocommit=True,
                # 15 minutes
                pool_recycle=60 * 15,
            )
            start_time: float = time.time()
            log.debug(
                "Connection MySQL db: %s, created time: [%0.3fs]",
                self.pool_settings.db,
                time.time() - start_time,
            )
            return self.pool
        except (ConnectionError, TimeoutError, aiomysql.OperationalError) as e:
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Mysql create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(self.container_settings.reconnect_timeout)
            await self.create_pool()
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Mysql create poll error:")
            raise e
