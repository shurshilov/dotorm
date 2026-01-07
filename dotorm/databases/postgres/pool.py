"""PostgreSQL connection pool management."""

import logging
import asyncio
import time

try:
    import asyncpg
except ImportError:
    ...

from .transaction import ContainerTransaction
from ..abstract.types import ContainerSettings, PostgresPoolSettings
from .session import NoTransactionNoPoolSession


log = logging.getLogger("dotorm")


class ContainerPostgres:
    """
    PostgreSQL connection pool container.

    Manages pool lifecycle and provides utilities
    for database and table creation.
    """

    def __init__(
        self,
        pool_settings: PostgresPoolSettings,
        container_settings: ContainerSettings,
    ):
        self.pool_settings = pool_settings
        self.container_settings = container_settings
        self.pool: "asyncpg.Pool | None" = None

    async def create_pool(self) -> "asyncpg.Pool":
        """Create connection pool with retry on failure."""
        try:
            start_time = time.time()
            pool = await asyncpg.create_pool(
                **self.pool_settings.model_dump(),
                min_size=5,
                max_size=15,
                command_timeout=60,
                # 15 minutes
                # max_inactive_connection_lifetime
                # pool_recycle=60 * 15,
            )
            assert pool is not None
            self.pool = pool

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
        ):
            log.exception(
                "Postgres create pool connection lost, reconnect after %d seconds",
                self.container_settings.reconnect_timeout,
            )
            await asyncio.sleep(self.container_settings.reconnect_timeout)
            return await self.create_pool()
        except Exception as e:
            log.exception("Postgres create pool error:")
            raise e

    async def close_pool(self):
        """Close connection pool."""
        if self.pool:
            # await self.pool.close()
            self.pool.terminate()
            self.pool = None

    async def create_database(self):
        """Create database if it doesn't exist."""
        db_to_create = self.pool_settings.database
        # Connect to default postgres database
        temp_settings = self.pool_settings.model_copy()
        temp_settings.database = "postgres"

        conn = await NoTransactionNoPoolSession.get_connection(temp_settings)
        sql = f'CREATE DATABASE "{db_to_create}"'
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    async def create_and_update_tables(self, models: list):
        """
        Create/update tables for given models.

        Args:
            models: List of DotModel classes
        """
        stmt_foreign_keys = []

        async with ContainerTransaction(self.pool) as session:
            # создаем модели в БД, без FK
            for model in models:
                foreign_keys = await model.__create_table__(session)
                stmt_foreign_keys += foreign_keys

            # создаем внешние ключи, для ссылочной целостности
            # на поля many2one а также на колонки полей many2many
            for stmt_foreign_key in stmt_foreign_keys:
                try:
                    await session.execute(stmt_foreign_key)
                except asyncpg.exceptions.DuplicateObjectError:
                    # FK already exists
                    pass
