import asyncio
import datetime
from typing import ClassVar, Self

from .databases.postgres.session import (
    PostgresSessionWithPool,
    PostgresSessionWithTransactionSingleConnection,
)

from .fields import Field, Many2many, Many2one, One2many, One2one
from .builder import Builder


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

    async def delete(self, session):
        stmt, values = await self.build_delete()
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    async def update(self, session, payload: Self | None = None, fields=[]):
        if not payload:
            payload = self
        stmt, values = await self.build_update(payload, fields)
        func_prepare = None
        func_cur = "fetchall"

        return await session.execute(stmt, values, func_prepare, func_cur)

    @classmethod
    async def get(cls, session, id, fields=[]):
        stmt, values = await cls.build_get(id, fields)
        func_prepare = cls.prepare_id
        func_cur = "fetchall"

        record = await session.execute(stmt, values, func_prepare, func_cur)
        assert record is not None
        assert isinstance(record, cls)
        return record

    @classmethod
    async def create(cls, session, payload):
        stmt, values = await cls.build_create(payload)
        func_prepare = None
        func_cur = "lastrowid"
        # совместимость с postgres
        if (
            type(session)
            == PostgresSessionWithTransactionSingleConnection | PostgresSessionWithPool
        ):
            stmt += " RETURNING id"

        record = await session.execute(stmt, values, func_prepare, func_cur)
        assert record is not None
        if (
            type(session)
            == PostgresSessionWithTransactionSingleConnection | PostgresSessionWithPool
        ):
            return record[0]["id"]
        return record

        # TODO: создание relations полей

    @classmethod
    async def search(
        cls,
        session,
        start=None,
        end=None,
        limit=None,
        order="DESC",
        sort="id",
        filter=None,
        fields=[],
        raw=None,
    ):
        stmt, values = await cls.build_search(
            start, end, limit, order, sort, filter, fields, raw
        )
        func_prepare = cls.prepare_ids if not raw else None
        func_cur = "fetchall"

        records = await session.execute(stmt, values, func_prepare, func_cur)
        assert records is not None
        return records

    @classmethod
    async def table_len(cls, session):
        stmt, values = await cls.build_table_len()
        func_prepare = lambda rows: [r["COUNT(*)"] for r in rows]
        if (
            type(session)
            == PostgresSessionWithTransactionSingleConnection | PostgresSessionWithPool
        ):
            func_prepare = lambda rows: [r["count"] for r in rows]
        func_cur = "fetchall"

        records = await session.execute(stmt, values, func_prepare, func_cur)
        assert records is not None
        if len(records):
            return records
        return []

    # RELASHIONSHIP
    @classmethod
    async def get_with_relations_concurrent(
        cls, session, id, fields=[], relation_fields=[]
    ):
        """Выполняется ПАРАЛЛЕЛЬНО в нескольких соединениях, без транзакций"""
        request_list, field_name_list, field_list = await cls.build_get_with_relations(
            id, fields, relation_fields
        )
        # первый запрос всегда build_get
        request_list[0] += (cls.prepare_id, "fetchall")

        for index in range(1, len(request_list)):
            field = field_list[index - 1]
            if isinstance(field, Many2many):
                request_list[index] += (field.relation_table.prepare_ids, "fetchall")
            elif isinstance(field, One2many):
                request_list[index] += (field.relation_table.prepare_ids, "fetchall")
            elif isinstance(field, One2one):
                request_list[index] += (field.relation_table.prepare_id, "fetchall")
            elif isinstance(field, Many2one):
                request_list[index] += (field.relation_table.prepare_id, "fetchall")

        # TODO: придумать механизм сборки нескольких запросов с func_prepare
        request_list = [
            session.execute(stmt=i[0], val=i[1], func_prepare=i[2], func_cur=i[3])
            for i in request_list
        ]

        # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
        results: list[cls] = await asyncio.gather(*request_list)

        # добавляем атрибуты к исходному обьекту,
        # получая удобное обращение через дот-нотацию
        record = results.pop(0)
        for field in results:
            setattr(record, field_name_list.pop(0), field)

        return record

    @classmethod
    async def get_with_relations(cls, session, id, fields=[], relation_fields=[]):
        """Выполняется ПОСЛЕДОВАТЕЛЬНО в нескольких соединениях, без транзакций"""
        request_list, field_name_list, field_list = await cls.build_get_with_relations(
            id, fields, relation_fields
        )
        # первый запрос всегда build_get
        request_list[0] += (cls.prepare_id, "fetchall")

        for index in range(1, len(request_list)):
            field = field_list[index - 1]
            if isinstance(field, Many2many):
                request_list[index] += (field.relation_table.prepare_ids, "fetchall")
            elif isinstance(field, One2many):
                request_list[index] += (field.relation_table.prepare_ids, "fetchall")
            elif isinstance(field, One2one):
                request_list[index] += (field.relation_table.prepare_id, "fetchall")
            elif isinstance(field, Many2one):
                request_list[index] += (field.relation_table.prepare_id, "fetchall")

        results = []
        # 1 conn
        for request in request_list:
            res = await session.execute(
                stmt=request[0],
                val=request[1],
                func_prepare=request[2],
                func_cur=request[3],
            )
            results.append(res)

        # добавляем атрибуты к исходному обьекту,
        # получая удобное обращение через дот-нотацию
        record = results.pop(0)
        for field in results:
            setattr(record, field_name_list.pop(0), field)

        return record

    async def update_with_relations(self, session, payload: Self, fields=[]):
        """Выполняется ПОСЛЕДОВАТЕЛЬНО в одном соединении"""
        request_list, field_list = await self.build_update_with_relations(
            payload, fields
        )

        # первый запрос всегда build_update
        request_list[0] += (None, "fetchall")

        for index in range(1, len(request_list)):
            field = field_list[index - 1]
            if isinstance(field, Many2many):
                request_list[index] += (None, "fetchall")
            elif isinstance(field, One2many):
                request_list[index] += (None, "fetchall")
            elif isinstance(field, One2one):
                request_list[index] += (None, "fetchall")
            elif isinstance(field, Many2one):
                request_list[index] += (None, "fetchall")

        # 1 conn
        results = tuple()
        for request in request_list:
            res = await session.execute(
                stmt=request[0],
                val=request[1],
                func_prepare=None,
                func_cur="fetchall",
            )
            results += tuple(res)
        return results

    async def update_one2one(self, session, fk_id, fields=[], fk="id"):
        stmt, values = await self.build_update_one2one(fk_id, fields, fk)
        func_prepare = None
        func_cur = "fetchall"

        res = await session.execute(stmt, values, func_prepare, func_cur)
        return res

    # TODO: universal
    @classmethod
    async def get_many2many(
        cls, session, id, comodel, relation, column1, column2, fields=[]
    ):
        stmt, values = await cls.build_get_many2many(
            id, comodel, relation, column1, column2, fields
        )
        func_prepare = comodel.prepare_ids
        func_cur = "fetchall"

        res = await session.execute(stmt, values, func_prepare, func_cur)
        return res

    @classmethod
    async def create_with_relations(cls, session, payload=None):
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

    @classmethod
    async def __create_table__(cls, session):
        # Метод для создания таблицы в базе данных, основанной на атрибутах класса.

        # Создаём список custom_fields для хранения определений полей таблицы.
        fields_created = []

        # Проходимся по атрибутам класса и извлекаем информацию о полях.
        for field_name, field in cls.get_fields().items():
            if isinstance(field, Field) and field.store and not field.relation:
                # Создаём строку с определением поля и добавляем её в список custom_fields.
                field_declaration = [f'"{field_name}" {field.sql_type}']

                if field.unique:
                    field_declaration.append("UNIQUE")
                if not field.null:
                    field_declaration.append("NOT NULL")
                if field.primary_key:
                    field_declaration.append("PRIMARY KEY")
                if field.default is not None:
                    field_declaration.append(f"DEFAULT {field.default}")

                fields_created.append(" ".join(field_declaration))

        # Создаём SQL-запрос для создания таблицы с определёнными полями.
        create_table_sql = f"""\
CREATE TABLE IF NOT EXISTS {cls.__table__} (\
{', '.join(fields_created)}\
);"""

        # Выполняем SQL-запрос.
        res = await session.execute(create_table_sql)
        return res
