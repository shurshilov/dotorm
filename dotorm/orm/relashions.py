import asyncio
from typing import Any, Literal, Self

from .many2many import OrmMany2many
from ..builder.request_builder import RequestBuilderForm, FilterTriplet
from ..fields import Many2many, Many2one, One2many


class OrmRelashions(OrmMany2many):
    @classmethod
    async def search(
        cls,
        fields: list[str] = ["id"],
        start: int | None = None,
        end: int | None = None,
        limit: int = 1000,
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
        filter: list[FilterTriplet] | None = None,
        raw: bool = False,
        session=None,
    ) -> list[Self]:
        if session is None:
            session = cls._get_db_session()
        stmt, values = await cls.build_search(
            fields, start, end, limit, order, sort, filter
        )
        func_prepare = cls.prepare_list_ids if not raw else None
        func_cur = "fetchall"

        records: list[Self] = await session.execute(
            stmt, values, func_prepare, func_cur
        )  # type: ignore

        # если есть хоть одна запись и вообще нужно читать поля связей
        fields_relation = [
            (name, field) for name, field in cls.get_relation_fields() if name in fields
        ]
        if records and fields_relation:
            await cls._records_list_get_relation(session, fields_relation, records)

        return records

    @classmethod
    async def get_with_relations(cls, id, fields=[], fields_info={}, session=None):
        """Выполняется ПАРАЛЛЕЛЬНО в нескольких соединениях, без транзакций"""
        # если нет сессии, взять сессию по умолчанию
        if session is None:
            session = cls._get_db_session()

        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [name for name in cls.get_store_fields() if name in fields]
        # если вдруг они не заданы, или таких нет, взять все
        if not fields_store:
            fields_store = [name for name in cls.get_store_fields()]
        if "id" not in fields_store:
            fields_store.append("id")

        stmt, values = await cls.build_get(id, fields_store)
        func_prepare = None
        func_cur = "fetchall"

        record_raw: list[Any] = await session.execute(
            stmt, values, func_prepare, func_cur
        )
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
                    fields = ["id"]
                    if relation_table.get_fields().get("name"):
                        fields.append("name")
                else:
                    fields = fields_nested

                if isinstance(field, Many2one) and relation_table:
                    # взять ид из поля many2one и запросить запись из связанной таблицы
                    m2o_id = getattr(record, name)
                    stmt, val = await relation_table.build_get(m2o_id, fields=fields)

                    req = RequestBuilderForm(
                        stmt=stmt,
                        value=val,
                        field_name=name,
                        field=field,
                        fields=fields,
                    )
                    request_list.append(req)
                    execute_list.append(
                        session.execute(
                            stmt=req.stmt,
                            val=req.value,
                            func_prepare=req.function_prepare,
                            func_cur=req.function_curcor,
                        )
                    )
                # если m2m или o2m необходимо посчтитать длину, для пагинации
                if isinstance(field, Many2many):
                    params = {
                        "id": record.id,
                        "comodel": relation_table,
                        "relation": field.many2many_table,
                        "column1": field.column1,
                        "column2": field.column2,
                        "fields": fields,
                        "order": "desc",
                        "start": 0,
                        "end": 40,
                        "sort": "id",
                        "limit": 40,
                        # "session": session,
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
                        fields=fields,
                    )
                    request_list.append(req)

                if isinstance(field, One2many) and relation_table:
                    params = {
                        "start": 0,
                        "end": 40,
                        "limit": 40,
                        "fields": fields,
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
                        fields=fields,
                    )
                    request_list.append(req)

            # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
            results = await asyncio.gather(*execute_list)

            # добавляем атрибуты к исходному обьекту,
            # получая удобное обращение через дот-нотацию
            i = 0
            for request_builder in request_list:
                result = results[i]
                if isinstance(request_builder.field, Many2one):
                    # m2o нужно распаковать так как он тоже в списке
                    # если пустой список, то установить None
                    result = result[0] if result else None
                if isinstance(request_builder.field, (Many2many, One2many)):
                    # если m2m или o2m необзодимо взять два результатата
                    # так как один из них это число всех строк таблицы
                    # для пагинации
                    fields_info = (
                        request_builder.field.relation_table.get_fields_info_list(
                            request_builder.fields
                        )
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

    async def update_with_relations(self, payload: Self, fields=[], session=None):
        """Выполняется ПОСЛЕДОВАТЕЛЬНО в одном соединении"""
        if session is None:
            session = self._get_db_session()

        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [name for name in self.get_store_fields() if name in fields]
        # Обновление сущности в базе без связей
        if fields_store:
            # fields_store = [name for name in self.get_store_fields()]
            stmt, values = await self.build_update(payload, self.id, fields_store)
            func_prepare = None
            func_cur = "fetchall"
            record_raw = await session.execute(stmt, values, func_prepare, func_cur)

        # защита, оставить только те поля, которые являются отношениями (m2m, o2m)
        # добавлена информаци о вложенных полях
        fields_relation = [
            (name, field)
            for name, field in self.get_relation_fields_m2m_o2m()
            if name in fields
        ]

        # если есть хоть одна запись и вообще нужно читать поля связей
        if fields_relation:
            request_list = []
            field_list = []
            for name, field in fields_relation:
                field_obj = getattr(payload, name)
                if isinstance(field, One2many):
                    field_list.append(field)
                    # заменить в связанных полях виртуальный ид на вновь созданный
                    for obj in field_obj["created"]:
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if isinstance(f, Many2one) and v == "VirtualId":
                                obj[k] = self.id

                    data_created = [
                        field.relation_table(**obj) for obj in field_obj["created"]  # type: ignore
                    ]
                    if field_obj["created"]:
                        request_list.append(
                            field.relation_table.create_bulk(data_created)
                        )
                    if field_obj["deleted"]:
                        request_list.append(
                            field.relation_table.delete_bulk(field_obj["deleted"])
                        )

                if isinstance(field, Many2many):
                    field_list.append(field)
                    # заменить в связанных полях виртуальный ид на вновь созданный
                    for obj in field_obj["created"]:
                        for k, v in obj.items():
                            f = getattr(field.relation_table, k)
                            if isinstance(f, Many2one) and v == "VirtualId":
                                obj[k] = self.id
                    data_created = [
                        field.relation_table(**obj) for obj in field_obj["created"]  # type: ignore
                    ]
                    if field_obj["created"]:
                        created_ids = await field.relation_table.create_bulk(
                            data_created
                        )
                        # здесь надо добавить результат создания
                        if "selected" not in field_obj:
                            field_obj["selected"] = []
                        field_obj["selected"] += [rec["id"] for rec in created_ids]
                    if field_obj.get("selected"):
                        data_selected = [(self.id, id) for id in field_obj["selected"]]
                        request_list.append(self.link_many2many(field, data_selected))
                    if field_obj.get("unselected"):
                        request_list.append(
                            self.unlink_many2many(field, field_obj["unselected"])
                        )

            # 1 conn
            results = tuple()
            for request in request_list:
                res = await asyncio.gather(request)
                results += tuple(res)
        return record_raw
