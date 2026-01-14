"""Relations ORM operations mixin."""

import asyncio
from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar

from ...decorators import hybridmethod

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol
    from ...model import DotModel

    _Base = DotModelProtocol
else:
    _Base = object

# TypeVar for generic payload - accepts any DotModel subclass
_M = TypeVar("_M", bound="DotModel")

from ...builder.request_builder import (
    FilterExpression,
    RequestBuilderForm,
)
from ...fields import (
    AttachmentMany2one,
    AttachmentOne2many,
    Many2many,
    Many2one,
    One2many,
    One2one,
)


class OrmRelationsMixin(_Base):
    """
    Mixin providing ORM operations for relations.

    Provides:
    - search - search records with relation loading
    - get_with_relations - get single record with relations
    - update_with_relations - update record with relations

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - __table__
    - get_fields(), get_store_fields(), get_relation_fields()
    - get_relation_fields_m2m_o2m(), get_relation_fields_attachment()
    - prepare_list_ids()
    - get_many2many(), link_many2many(), unlink_many2many()
    - _records_list_get_relation()
    - update()
    """

    @hybridmethod
    async def search(
        self,
        fields: list[str] = ["id"],
        start: int | None = None,
        end: int | None = None,
        limit: int = 1000,
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
        filter: FilterExpression | None = None,
        raw: bool = False,
        session=None,
    ) -> list[Self]:
        cls = self.__class__
        session = cls._get_db_session(session)

        # Use dialect from class
        dialect = cls._dialect

        stmt, values = cls._builder.build_search(
            fields, start, end, limit, order, sort, filter
        )
        prepare = cls.prepare_list_ids if not raw else None
        records: list[Self] = await session.execute(
            stmt, values, prepare=prepare
        )

        # если есть хоть одна запись и вообще нужно читать поля связей
        fields_relation = [
            (name, field)
            for name, field in cls.get_relation_fields()
            if name in fields
        ]
        if records and fields_relation:
            await cls._records_list_get_relation(
                session, fields_relation, records
            )

        return records

    @classmethod
    async def get_with_relations(
        cls,
        id,
        fields=None,
        fields_info={},
        session=None,
    ) -> Self | None:
        """Get record with relations loaded."""
        if not fields:
            fields = []
        session = cls._get_db_session(session)

        dialect = cls._dialect

        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [
            name for name in cls.get_store_fields() if name in fields
        ]
        # если вдруг они не заданы, или таких нет, взять все
        if not fields_store:
            fields_store = [name for name in cls.get_store_fields()]
        if "id" not in fields_store:
            fields_store.append("id")

        stmt, values = cls._builder.build_get(id, fields_store)
        record_raw: list[Any] = await session.execute(stmt, values)
        if not record_raw:
            return None
        record = cls(**record_raw[0])

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m, m2o)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field, fields_info.get(name))
            for name, field in cls.get_relation_fields()
            if name in fields
        ]

        # если есть хоть одна запись и вообще нужно читать поля связей
        if record and fields_relation:
            request_list = []
            execute_list = []

            # добавить запрос на o2m
            for name, field, fields_nested in fields_relation:
                relation_table = field.relation_table
                relation_table_field = field.relation_table_field

                if not fields_nested and relation_table:
                    fields_select = ["id"]
                    if relation_table.get_fields().get("name"):
                        fields_select.append("name")
                    if isinstance(field, AttachmentMany2one):
                        fields_select = (
                            relation_table.get_store_fields_omit_m2o()
                        )
                else:
                    fields_select = fields_nested

                if (
                    isinstance(field, (Many2one, AttachmentMany2one))
                    and relation_table
                ):
                    m2o_id = getattr(record, name)
                    stmt, val = relation_table._builder.build_get(
                        m2o_id, fields=fields_select
                    )
                    req = RequestBuilderForm(
                        stmt=stmt,
                        value=val,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)
                    execute_list.append(
                        session.execute(
                            req.stmt,
                            req.value,
                            prepare=req.function_prepare,
                            cursor=req.function_cursor,
                        )
                    )
                # если m2m или o2m необходимо посчитать длину, для пагинации
                if isinstance(field, Many2many):
                    params = {
                        "id": record.id,
                        "comodel": relation_table,
                        "relation": field.many2many_table,
                        "column1": field.column1,
                        "column2": field.column2,
                        "fields": fields_select,
                        "order": "desc",
                        "start": 0,
                        "end": 40,
                        "sort": "id",
                        "limit": 40,
                    }
                    # records
                    execute_list.append(cls.get_many2many(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = None
                    # len
                    execute_list.append(cls.get_many2many(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

                if isinstance(field, One2many) and relation_table:
                    params = {
                        "start": 0,
                        "end": 40,
                        "limit": 40,
                        "fields": fields_select,
                        "filter": [(relation_table_field, "=", record.id)],
                    }
                    execute_list.append(relation_table.search(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = 1000
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

                if isinstance(field, AttachmentOne2many) and relation_table:
                    params = {
                        "start": 0,
                        "end": 40,
                        "limit": 40,
                        "fields": relation_table.get_store_fields_omit_m2o(),
                        "filter": [
                            ("res_id", "=", record.id),
                            ("res_model", "=", record.__table__),
                        ],
                    }
                    execute_list.append(relation_table.search(**params))
                    params["fields"] = ["id"]
                    params["start"] = None
                    params["end"] = None
                    params["limit"] = 1000
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=relation_table.get_store_fields_omit_m2o(),
                    )
                    request_list.append(req)

                if isinstance(field, One2one) and relation_table:
                    params = {
                        "limit": 1,
                        "fields": fields_select,
                        "filter": [(relation_table_field, "=", record.id)],
                    }
                    execute_list.append(relation_table.search(**params))
                    req = RequestBuilderForm(
                        stmt=None,
                        value=None,
                        field_name=name,
                        field=field,
                        fields=fields_select,
                    )
                    request_list.append(req)

            # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
            results = await asyncio.gather(*execute_list)

            # добавляем атрибуты к исходному объекту,
            # получая удобное обращение через дот-нотацию
            i = 0
            for request_builder in request_list:
                result = results[i]

                if isinstance(
                    request_builder.field,
                    (Many2one, AttachmentMany2one, One2one),
                ):
                    # m2o нужно распаковать так как он тоже в списке
                    # если пустой список, то установить None
                    result = result[0] if result else None

                if isinstance(
                    request_builder.field,
                    (Many2many, One2many, AttachmentOne2many),
                ):
                    # если m2m или o2m необбзодимо взять два результатата
                    # так как один из них это число всех строк таблицы
                    # для пагинации
                    fields_info = request_builder.field.relation_table.get_fields_info_list(
                        request_builder.fields
                    )
                    result = {
                        "data": result,
                        "fields": fields_info,
                        "total": len(results[i + 1]),
                    }
                    i += 1

                setattr(record, request_builder.field_name, result)
                i += 1

        return record

    async def update_with_relations(
        self, payload: _M, fields=[], session=None
    ):
        """Update record with relations."""
        session = self._get_db_session(session)

        # Handle attachments
        fields_attachments = [
            (name, field)
            for name, field in self.get_relation_fields_attachment()
            if name in fields
        ]

        if fields_attachments:
            for name, field in fields_attachments:
                if isinstance(field, AttachmentMany2one):
                    field_obj = getattr(payload, name)
                    if field_obj and field.relation_table:
                        # TODO: всегда создавать новую строку аттачмент с файлом
                        # также надо продумать механизм обновления уже существующего файла
                        # надо ли? или проще удалять
                        field_obj["res_id"] = self.id
                        # Оборачиваем dict в объект модели
                        attachment_payload = field.relation_table(**field_obj)
                        attachment_id = await field.relation_table.create(
                            attachment_payload, session
                        )
                        setattr(payload, name, attachment_id)

        # Update stored fields
        fields_store = [
            name for name in self.get_store_fields() if name in fields
        ]
        # Обновление сущности в базе без связей
        if fields_store:
            record_raw = await self.update(payload, fields, session)

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field)
            for name, field in self.get_relation_fields_m2m_o2m()
            if name in fields
        ]

        if fields_relation:
            request_list = []
            field_list = []

            for name, field in fields_relation:
                field_obj = getattr(payload, name)

                if isinstance(field, One2one):
                    params = {
                        "limit": 1,
                        "fields": ["id"],
                        "filter": [(field.relation_table_field, "=", self.id)],
                    }
                    record = await field.relation_table.search(**params)
                    if len(record):
                        request_list.append(record[0].update(field_obj))

                if isinstance(field, (One2many, AttachmentOne2many)):
                    field_list.append(field)
                    # заменить в связанных полях виртуальный ид на вновь созданный
                    for obj in field_obj["created"]:
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if (
                                isinstance(f, (Many2one, AttachmentMany2one))
                                and v == "VirtualId"
                            ):
                                obj[k] = self.id

                    data_created = [
                        field.relation_table(**obj)
                        for obj in field_obj["created"]
                    ]

                    if isinstance(field, AttachmentOne2many):
                        for obj in data_created:
                            obj.res_id = self.id

                    if field_obj["created"]:
                        request_list.append(
                            field.relation_table.create_bulk(data_created)
                        )
                    if field_obj["deleted"]:
                        request_list.append(
                            field.relation_table.delete_bulk(
                                field_obj["deleted"]
                            )
                        )

                if isinstance(field, Many2many):
                    field_list.append(field)

                    # Replace virtual ID
                    for obj in field_obj["created"]:
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if (
                                isinstance(f, (Many2one, AttachmentMany2one))
                                and v == "VirtualId"
                            ):
                                obj[k] = self.id

                    data_created = [
                        field.relation_table(**obj)
                        for obj in field_obj["created"]
                    ]

                    if field_obj["created"]:
                        created_ids = await field.relation_table.create_bulk(
                            data_created
                        )
                        if "selected" not in field_obj:
                            field_obj["selected"] = []
                        field_obj["selected"] += [
                            rec["id"] for rec in created_ids
                        ]

                    if field_obj.get("selected"):
                        data_selected = [
                            (self.id, id) for id in field_obj["selected"]
                        ]
                        request_list.append(
                            self.link_many2many(field, data_selected)
                        )

                    if field_obj.get("unselected"):
                        request_list.append(
                            self.unlink_many2many(
                                field, field_obj["unselected"]
                            )
                        )

            # 1 conn
            results = tuple()
            for request in request_list:
                res = await asyncio.gather(request)
                results += tuple(res)

        return record_raw
