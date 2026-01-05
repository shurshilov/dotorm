from typing import Self

from ..databases.postgres.session import NoTransactionSession, PostgresSession
from ..builder.primary import BuilderCRUDPrimary


class OrmPrimary(BuilderCRUDPrimary):
    @staticmethod
    def _is_postgres(session):
        return PostgresSession in type(session).__bases__

    @classmethod
    def _is_postgres_pool(cls):
        # return PostgresSession in type(session).__bases__
        return cls._pool == NoTransactionSession

    async def delete(self, session=None):
        if session is None:
            session = self._get_db_session()
        stmt = await self.build_delete()
        values = [self.id]
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    @classmethod
    async def delete_bulk(cls, ids: list[int], session=None):
        if session is None:
            session = cls._get_db_session()
        stmt = await cls.build_delete_bulk(len(ids))
        values = ids
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    async def update(self, payload: Self | None = None, fields=[], session=None):
        if session is None:
            session = self._get_db_session()
        if not payload:
            payload = self
        stmt, values = await self.build_update(payload, self.id, fields)
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    @classmethod
    async def update_bulk(
        cls, ids: list[int], payload: Self | None = None, session=None
    ):
        if session is None:
            session = cls._get_db_session()
        stmt, values = await cls.build_update_bulk(payload, ids)
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    @classmethod
    async def create(cls, payload, session=None):
        if session is None:
            session = cls._get_db_session()
        stmt, values = await cls.build_create(payload)
        func_prepare = None
        func_cur = "lastrowid"
        # совместимость с postgres
        if cls._is_postgres(session):
            stmt += " RETURNING id"
            func_cur = "fetch"

        # TODO: создание relations полей
        record = await session.execute(stmt, values, func_prepare, func_cur)
        assert record is not None
        if cls._is_postgres(session):
            return record[0]["id"]
        return record

    @classmethod
    async def create_bulk(cls, payload, session=None):
        if session is None:
            session = cls._get_db_session()
        stmt, values, fields_returning = await cls.build_create_bulk(payload)
        func_prepare = None
        # func_cur = "executemany"
        func_cur = "fetch"
        # func_cur = "lastrowid"
        # совместимость с postgres
        if cls._is_postgres(session):
            stmt += f""" (SELECT {fields_returning} FROM
                unnest($1::{cls.__table__}[]) as r
            ) RETURNING id"""

        # TODO: создание relations полей
        record = await session.execute(stmt, [values], func_prepare, func_cur)
        return record

    @classmethod
    async def get(cls, id, fields: list[str] = [], session=None):
        if session is None:
            session = cls._get_db_session()
        dialect = "postgres"
        if not cls._is_postgres:
            dialect = "mysql"
        stmt, values = await cls.build_get(id, fields, dialect=dialect)
        func_prepare = cls.prepare_form_id
        func_cur = "fetchall"

        record = await session.execute(stmt, values, func_prepare, func_cur)
        if not record:
            return None
        assert isinstance(record, cls)
        return record

    @classmethod
    async def table_len(cls, session=None) -> int:
        if session is None:
            session = cls._get_db_session()
        stmt, values = await cls.build_table_len()
        func_prepare = lambda rows: [r["COUNT(*)"] for r in rows]
        if cls._is_postgres(session):
            func_prepare = lambda rows: [r["count"] for r in rows]
        func_cur = "fetchall"

        records = await session.execute(stmt, values, func_prepare, func_cur)
        assert records is not None
        if len(records):
            return records[0]
        return 0
