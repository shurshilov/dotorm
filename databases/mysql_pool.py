import logging

log = logging.getLogger("dotorm")
import asyncio
import time

import aiomysql


class MysqlPool:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    # РАБОТА С ПУЛОМ
    async def mysql_connect(self, settings):
        try:
            start_time: float = time.time()
            self.mysql_pool_no_auto_commit = await aiomysql.create_pool(
                minsize=5,
                maxsize=15,
                host=settings.db_portal_host,
                port=settings.db_portal_port,
                user=settings.db_portal_user,
                password=settings.db_portal_password,
                db=settings.db_portal_database,
                autocommit=False,
                # 15 minutes
                pool_recycle=60 * 15,
            )
            start_time: float = time.time()
            self.mysql_pool = await aiomysql.create_pool(
                minsize=6,
                maxsize=15,
                host=settings.db_portal_host,
                port=settings.db_portal_port,
                user=settings.db_portal_user,
                password=settings.db_portal_password,
                db=settings.db_portal_database,
                autocommit=True,
                # 15 minutes
                pool_recycle=60 * 15,
            )

            log.debug(
                "Connection MySQL db: %s, created time: [%0.3fs]",
                settings.db_portal_database,
                time.time() - start_time,
            )
            return self
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


mysqlPoolObject = MysqlPool()
