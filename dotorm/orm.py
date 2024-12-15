import asyncio
import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, Type, Union

from .databases.mysql.session import MysqlSessionWithPool

if TYPE_CHECKING:
    import aiomysql
    import asyncpg

from .builder.utils import FilterTriplet, RequestBuilderForm

from .databases.postgres.session import (
    PostgresSessionWithPool,
    PostgresSessionWithTransactionSingleConnection,
)
from .fields import Field, Many2many, Many2one, One2many, One2one
from .builder.builder import Builder


class DotModel(Builder):
    """Паттерн репозиторий, позволяет не зависить коду от орм/БД.
    только используется не через инверсию зависимостей, а через наследование.
    сессия может передаваться через инверсию зависимостей в случае с работой
    транзакций. Но для паралелльного выполнения вставок в транзакции необходимо удалить FK.
    тоесть вставка происходит через N соединений и при этом может откатиться.
    """

    _CACHE_DATA: ClassVar[dict] = {}
    _CACHE_LAST_TIME: ClassVar[dict] = {}

    @staticmethod
    def _is_postgres(session):
        return type(session) in [
            PostgresSessionWithTransactionSingleConnection,
            PostgresSessionWithPool,
        ]

    @staticmethod
    def cache(name, ttl=30):
        """Реализация простого кеша на TTL секунд, таблиц которые редко меняются,
        и делать запрос в БД не целесообразно каждый раз, можно сохранить результат.
        При использовании более одного воркера необходимо использовать redis.

        Arguments:
            name -- name cache store data
            ttl -- seconds cache store
        """

        def decorator(func):
            async def wrapper(self, *args):
                # если данные есть в кеше
                if self._CACHE_DATA.get(name):
                    time_diff = datetime.datetime.now() - self._CACHE_LAST_TIME[name]
                    # проверить актуальные ли они
                    if time_diff.seconds < ttl:
                        # если актуальные вернуть их
                        return self._CACHE_DATA[name]

                # если данных нет или они не актуальные сделать запрос в БД и запомнить
                self._CACHE_DATA[name] = await func(self, *args)
                # также сохранить дату и время запроса, для последующей проверки
                self._CACHE_LAST_TIME[name] = datetime.datetime.now()
                return self._CACHE_DATA[name]

            return wrapper

        return decorator

    # async def __getattr__(self, name):
    #     field = getattr(self, name)
    #     # if isinstance(field, Field):
    #     if isinstance(field, (Many2many, Many2one, One2many)):
    #         value = await self.get_with_relations(self.id, fields=[name])
    #         setattr(self, name, value)
    #         return value
    #     else:
    #         raise "NOT ATTR FOUND"
    # else:
    #     return field

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
    async def get(cls, id, fields: list[str] = [], session=None):
        if session is None:
            session = cls._get_db_session()
        stmt, values = await cls.build_get(id, fields)
        func_prepare = cls.prepare_form_id
        func_cur = "fetchall"

        record = await session.execute(stmt, values, func_prepare, func_cur)
        if not record:
            return None
        assert isinstance(record, cls)
        return record

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
    async def link_many2many(cls, field: Many2many, values: list, session=None):
        if session is None:
            session = cls._get_db_session()
        # values_tuple = []
        # for id in values:
        #     values_tuple.append(tuple(id))
        query_placeholders = ", ".join(["%s"] * len(values[0]))
        stmt = f"""INSERT INTO {field.many2many_table}
        ({field.column2}, {field.column1})
        VALUES
        ({query_placeholders})
        """
        #         query_placeholders = ", ".join(["%s"] * len(values_list))
        # stmt = f"INSERT INTO {cls.__table__} ({query_columns}) VALUES ({query_placeholders})"
        func_prepare = None
        func_cur = "executemany"
        record = await session.execute(stmt, [values], func_prepare, func_cur)
        return record

    @classmethod
    async def unlink_many2many(cls, field: Many2many, ids: list, session=None):
        if session is None:
            session = cls._get_db_session()
        args: str = ",".join(["%s"] * len(ids))
        stmt = f"DELETE FROM {field.many2many_table} WHERE {field.column1} in ({args})"
        values = ids
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

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
    ):
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
    async def _records_list_get_relation(cls, session, fields_relation, records):
        request_list = await cls.build_search_relation(fields_relation, records)
        execute_list = [
            session.execute(
                stmt=req.stmt,
                val=req.value,
                func_prepare=req.function_prepare,
                func_cur=req.function_curcor,
            )
            for req in request_list
        ]
        # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
        results = await asyncio.gather(*execute_list)

        # маппинг (полученных оптимизированных запросов) полей связей
        # на конкретные записи (полученные при чтении store на предыдущем шаге)
        for index, result in enumerate(results):
            req = request_list[index]
            if isinstance(req.field, Many2one):
                for rec in records:
                    rec_field_raw = getattr(rec, req.field_name)
                    for res_model in result:
                        if rec_field_raw == res_model.id:
                            setattr(rec, req.field_name, res_model)
            if isinstance(req.field, One2many):
                for rec in records:
                    for res_model in result:
                        res_field_id = getattr(
                            res_model, req.field.relation_table_field
                        )
                        if rec.id == res_field_id:
                            old_value = getattr(rec, req.field_name)
                            # если еще не задано то пустой список
                            if isinstance(old_value, Field):
                                old_value = []
                            # иначе добавляем ид в список
                            old_value.append(res_model)
                            setattr(rec, req.field_name, old_value)
            if isinstance(req.field, Many2many):
                for rec in records:
                    for res_model in result:
                        if rec.id == res_model.m2m_id:
                            old_value = getattr(rec, req.field_name)
                            # если еще не задано то пустой список
                            if isinstance(old_value, Field):
                                old_value = []
                            # иначе добавляем ид в список
                            old_value.append(res_model)
                            setattr(rec, req.field_name, old_value)
                for res_model in result:
                    # удалить атрибут m2m_id
                    del res_model.__dict__["m2m_id"]

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

    # RELASHIONSHIP
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
                if not fields_nested:
                    fields = ["id"]
                    if relation_table.get_fields().get("name"):
                        fields.append("name")
                else:
                    fields = fields_nested

                if isinstance(field, Many2one):
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

                if isinstance(field, One2many):
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

    # @classmethod
    # async def get_with_relations(cls, session, id, fields=[], relation_fields=[]):
    #     """Выполняется ПОСЛЕДОВАТЕЛЬНО в нескольких соединениях, без транзакций"""
    #     request_list, field_name_list, field_list = await cls.build_get_with_relations(
    #         id, fields, relation_fields
    #     )
    #     # первый запрос всегда build_get
    #     request_list[0] += (cls.prepare_form_id, "fetchall")

    #     for index in range(1, len(request_list)):
    #         field = field_list[index - 1]
    #         if isinstance(field, Many2many):
    #             request_list[index] += (
    #                 field.relation_table.prepare_form_ids,
    #                 "fetchall",
    #             )
    #         elif isinstance(field, One2many):
    #             request_list[index] += (
    #                 field.relation_table.prepare_form_ids,
    #                 "fetchall",
    #             )
    #         elif isinstance(field, One2one):
    #             request_list[index] += (
    #                 field.relation_table.prepare_form_id,
    #                 "fetchall",
    #             )
    #         elif isinstance(field, Many2one):
    #             request_list[index] += (
    #                 field.relation_table.prepare_form_id,
    #                 "fetchall",
    #             )

    #     results = []
    #     # 1 conn
    #     for request in request_list:
    #         res = await session.execute(
    #             stmt=request[0],
    #             val=request[1],
    #             func_prepare=request[2],
    #             func_cur=request[3],
    #         )
    #         results.append(res)

    #     # добавляем атрибуты к исходному обьекту,
    #     # получая удобное обращение через дот-нотацию
    #     record = results.pop(0)
    #     for field in results:
    #         setattr(record, field_name_list.pop(0), field)

    #     return record

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

    @classmethod
    async def create_with_relations(cls, payload=None, session=None):
        if session is None:
            session = cls._get_db_session()
        request_list = await cls.build_create_with_relations(payload)
        request_list = [
            session.execute(stmt=i[0], val=i[1], func_prepare=None, func_cur="fetchall")
            for i in request_list
        ]
        # 1 conn
        results = tuple()
        for request in request_list:
            results += tuple(await request)
        return results

    # async def create_one2one(cls, fk_id=None, fk="id", session=None):
    #     stmt, values, func_prepare, func_cur = await cls.build_create_one2one(fk_id, fk)
    #     if session:
    #         res = await session.execute(stmt, values, func_prepare, func_cur)
    #     else:
    #         res = await cls._transaction.execute(stmt, values, func_prepare, func_cur)
    #     return res

    async def update_one2one(self, fk_id, fields=[], fk="id", session=None):
        if session is None:
            session = self._get_db_session()
        stmt, values = await self.build_update_one2one(fk_id, fields, fk)
        func_prepare = None
        func_cur = "fetchall"

        res = await session.execute(stmt, values, func_prepare, func_cur)
        return res

    # @classmethod
    # async def create_many2many(cls, field, ids):
    # TODO: universal
    @classmethod
    async def get_many2many(
        cls,
        id,
        comodel,
        relation,
        column1,
        column2,
        fields=[],
        order: Literal["desc", "asc"] = "desc",
        start: int | None = None,
        end: int | None = None,
        sort: str = "id",
        limit: int | None = 10,
        session=None,
    ):
        if session is None:
            session = cls._get_db_session()
        # защита, оставить только те поля, которые действительно хранятся в базе
        fields_store = [name for name in cls.get_store_fields() if name in fields]
        stmt, values = await cls.build_get_many2many(
            id,
            comodel,
            relation,
            column1,
            column2,
            fields_store,
            order,
            start,
            end,
            sort,
            limit,
        )
        func_prepare = comodel.prepare_list_ids
        func_cur = "fetchall"

        records = await session.execute(stmt, values, func_prepare, func_cur)

        # если есть хоть одна запись и вообще нужно читать поля связей
        fields_relation = [
            (name, field)
            for name, field in comodel.get_relation_fields()
            if name in fields
        ]
        if records and fields_relation:
            await cls._records_list_get_relation(session, fields_relation, records)
        return records

    # @classmethod
    # async def __create_new_fields__(cls, session):
    #     """Создает новые поля, если таблица уже создана в базе данных,
    #     но после этого добавили новые поля"""

    @classmethod
    async def __create_table__(cls, session=None):
        """Метод для создания таблицы в базе данных, основанной на атрибутах класса."""
        if session is None:
            session = cls._get_db_session()

        # описание поля для создания в бд со всеми аттрибутами
        fields_created_declaration: list[str] = []
        # только текстовые названия полей
        fields_created: list = []
        # готовый запрос на добавления FK
        many2one_fields_fk: list[str] = []

        # Проходимся по атрибутам класса и извлекаем информацию о полях.
        for field_name, field in cls.get_fields().items():
            if isinstance(field, Field):
                if (field.store and not field.relation) or isinstance(field, Many2one):
                    # Создаём строку с определением поля и добавляем её в список custom_fields.
                    field_declaration = [f'"{field_name}" {field.sql_type}']

                    if field.unique:
                        field_declaration.append("UNIQUE")
                    if not field.null:
                        field_declaration.append("NOT NULL")
                    if field.primary_key:
                        field_declaration.append("PRIMARY KEY")
                    if field.default is not None:
                        if isinstance(field.default, (bool, int, str)):
                            field_declaration.append(f"DEFAULT {field.default}")

                    if isinstance(field, Many2one):
                        # не забыть создать FK для many2one
                        # ALTER TABLE %s ADD FOREIGN KEY (%s) REFERENCES %s(%s) ON DELETE %s",
                        many2one_fields_fk.append(
                            f"ALTER TABLE IF EXISTS {cls.__table__} ADD FOREIGN KEY ({field_name}) REFERENCES {field.relation_table.__table__}(id) ON DELETE {field.ondelete}"
                        )

                    field_declaration_str = " ".join(field_declaration)
                    fields_created_declaration.append(field_declaration_str)
                    fields_created.append([field_name, field_declaration_str])

                # создаем промежуточную таблицу для many2many
                if field.relation and isinstance(field, Many2many):
                    column1 = f'"{field.column1}" INTEGER NOT NULL'
                    column2 = f'"{field.column2}" INTEGER NOT NULL'
                    # COMMENT ON TABLE {field.many2many_table} IS f"RELATION BETWEEN {model._table} AND {comodel._table}";
                    # CREATE INDEX ON {field.many2many_table} ({field.column1}, {field.column2});
                    # PRIMARY KEY({field.column1}, {field.column2})
                    create_table_sql = f"""\
                    CREATE TABLE IF NOT EXISTS {field.many2many_table} (\
                    {', '.join([column1, column2])}\
                    );
                    """
                    res = await session.execute(create_table_sql)

        # Создаём SQL-запрос для создания таблицы с определёнными полями.
        create_table_sql = f"""\
CREATE TABLE IF NOT EXISTS {cls.__table__} (\
{', '.join(fields_created_declaration)}\
);"""

        # если таблицы уже были созданы, но появились новые поля
        # необходимо их добавить
        for field_name, field_declaration in fields_created:
            sql = f"""SELECT column_name FROM information_schema.columns
WHERE table_name='{cls.__table__}' and column_name='{field_name}';"""

            field_exist = await session.execute(sql)
            if field_exist == "SELECT 0":
                await session.execute(
                    f"""ALTER TABLE {cls.__table__} ADD COLUMN {field_declaration};"""
                )

        # Выполняем SQL-запрос.
        res = await session.execute(create_table_sql)
        return many2one_fields_fk
