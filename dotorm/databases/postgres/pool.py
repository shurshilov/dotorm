import logging
import asyncio
import asyncpg
import time

from .transaction import ContainerTransaction
from ...orm.model import DotModel
from .session import NoTransactionNoPoolSession
from ..abstract.types import ContainerSettings, PostgresPoolSettings


log = logging.getLogger("dotorm")


class ContainerPostgres:
    def __init__(
        self,
        pool_settings: PostgresPoolSettings,
        container_settings: ContainerSettings,
    ):
        self.pool_settings = pool_settings
        self.container_settings = container_settings

    # РАБОТА С ПУЛОМ
    async def create_pool(self):
        try:
            start_time: float = time.time()
            pool = await asyncpg.create_pool(
                **self.pool_settings.model_dump(),
                min_size=5,
                max_size=15,
                command_timeout=60,
                # 15 minutes
                # max_inactive_connection_lifetime
                # pool_recycle=60 * 15,
            )
            # assert isinstance(pool, asyncpg.Pool)
            assert pool is not None
            self.pool = pool
            start_time: float = time.time()

            log.debug(
                "Connection PostgreSQL db: %s, created time: [%0.3fs]",
                self.pool_settings.database,
                time.time() - start_time,
            )
            return self.pool
        except (
            ConnectionError,
            TimeoutError,
            asyncpg.exceptions.ConnectionFailureError,
        ) as e:
            # Если не смогли подключиться к базе пробуем переподключиться
            log.exception(
                "Postgres create poll connection lost, reconnect after 10 seconds: "
            )
            await asyncio.sleep(self.container_settings.reconnect_timeout)
            await self.create_pool()
        except Exception as e:
            # если ошибка не связанна с сетью, завершаем выполнение программы
            log.exception("Postgres create pool error:")
            raise e

    async def create_database(self):
        """Создание БД
        pool_settings["database"] = "template1"
        pool_settings["user"] = "postgres"
        f'CREATE DATABASE "{db_config.database}" OWNER "{db_config.user}"'
        """
        db_to_create = self.pool_settings.database
        self.pool_settings.database = "postgres"
        conn = await NoTransactionNoPoolSession.get_connection(self.pool_settings)
        sql = f'CREATE DATABASE "{db_to_create}"'
        await conn.execute(sql)
        await conn.close()

    async def create_and_update_tables(self, models: list[type[DotModel]]):
        "Синхронизация таблиц в БД"
        stmt_foreign_keys = []

        async with ContainerTransaction(self.pool) as session:
            # создаем модели в БД, без FK
            for model in models:
                foreign_keys = await model.__create_table__(session)
                stmt_foreign_keys += foreign_keys

            # создаем внешние ключи, для ссылочной целостности
            # на поля many2one а также на колонки полей many2many
            for stmt_foreign_key in stmt_foreign_keys:
                await session.execute(stmt_foreign_key)
