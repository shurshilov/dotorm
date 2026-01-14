"""Primary ORM operations mixin."""

from typing import TYPE_CHECKING, Self, TypeVar

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol
    from ...model import DotModel

    _Base = DotModelProtocol
else:
    _Base = object

from ...components.dialect import POSTGRES
from ...model import JsonMode
from ...decorators import hybridmethod


# TypeVar for generic payload - accepts any DotModel subclass
_M = TypeVar("_M", bound="DotModel")


class OrmPrimaryMixin(_Base):
    """
    Mixin providing primary CRUD ORM operations.

    Provides:
    - create, create_bulk
    - get, table_len
    - update, update_bulk
    - delete, delete_bulk

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - __table__
    - prepare_form_id()
    """

    async def delete(self, session=None):
        session = self._get_db_session(session)
        stmt = self._builder.build_delete()
        return await session.execute(stmt, [self.id])

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
        cls = self.__class__
        session = cls._get_db_session(session)
        stmt = cls._builder.build_delete_bulk(len(ids))
        return await session.execute(stmt, ids)

    async def update(
        self,
        payload: "_M | None" = None,
        fields=None,
        session=None,
    ):
        session = self._get_db_session(session)
        if payload is None:
            payload = self
        if not fields:
            fields = []

        # Сериализация в ORM слое, а не в Builder
        if fields:
            payload_dict = payload.json(
                include=set(fields),
                exclude_none=True,
                only_store=True,
                mode=JsonMode.UPDATE,
            )
        else:
            payload_dict = payload.json(
                exclude=payload.get_none_update_fields_set(),
                exclude_none=True,
                exclude_unset=True,
                only_store=True,
                mode=JsonMode.UPDATE,
            )

        stmt, values = self._builder.build_update(payload_dict, self.id)
        return await session.execute(stmt, values)

    @hybridmethod
    async def update_bulk(
        self,
        ids: list[int],
        payload: _M,
        session=None,
    ):
        cls = self.__class__
        session = cls._get_db_session(session)

        # Сериализация в ORM слое
        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            exclude_none=True,
            exclude_unset=True,
            only_store=True,
        )

        stmt, values = cls._builder.build_update_bulk(payload_dict, ids)
        return await session.execute(stmt, values)

    @hybridmethod
    async def create(self, payload: _M, session=None) -> int:
        cls = self.__class__
        session = cls._get_db_session(session)

        # Сериализация в ORM слое
        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            exclude_none=True,
            only_store=True,
            mode=JsonMode.CREATE,
        )

        stmt, values = cls._builder.build_create(payload_dict)

        # Use dialect instead of _is_postgres
        if cls._dialect.supports_returning:
            stmt += " RETURNING id"
            record = await session.execute(stmt, values, cursor="fetch")
            assert record is not None
            return record[0]["id"]

        # TODO: создание relations полей
        record = await session.execute(stmt, values, cursor="lastrowid")
        assert record is not None
        return record

    @hybridmethod
    async def create_bulk(self, payload: list[_M], session=None):
        cls = self.__class__
        session = cls._get_db_session(session)

        # Исключаем primary_key поля
        exclude_fields = {
            name
            for name, field in cls.get_fields().items()
            if field.primary_key
        }

        # Сериализация
        payloads_dicts = [
            p.json(
                exclude=exclude_fields, only_store=True, mode=JsonMode.CREATE
            )
            for p in payload
        ]

        stmt, values = cls._builder.build_create_bulk(payloads_dicts)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"

        records = await session.execute(stmt, values, cursor="fetch")
        return records

    @hybridmethod
    async def get(self, id, fields: list[str] = [], session=None) -> Self:
        cls = self.__class__
        session = cls._get_db_session(session)

        stmt, values = cls._builder.build_get(id, fields)
        record = await session.execute(
            stmt, values, prepare=cls.prepare_form_id
        )

        if not record:
            # return None
            raise ValueError("Record not found")
        assert isinstance(record, cls)
        return record

    @hybridmethod
    async def table_len(self, session=None) -> int:
        cls = self.__class__
        session = cls._get_db_session(session)
        stmt, values = cls._builder.build_table_len()

        # Use dialect for column name
        if cls._dialect == POSTGRES:
            prepare = lambda rows: [r["count"] for r in rows]
        else:
            prepare = lambda rows: [r["COUNT(*)"] for r in rows]

        records = await session.execute(stmt, values, prepare=prepare)
        assert records is not None
        if len(records):
            return records[0]
        return 0
