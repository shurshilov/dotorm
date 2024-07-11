import asyncio
import datetime
from typing import Self

from .databases.postgres.transaction import TransactionPostgresDotORM
from .fields import Field
from .builder import Builder


class DotModel(Builder):
    """Паттерн репозиторий, позволяет не зависить коду от орм/БД.
    только используется не через инверсию зависимостей, а через наследование.
    сессия может передаваться через инверсию зависимостей в случае с работой
    транзакций. Но для паралелльного выполнения вставок в транзакции необходимо удалить FK.
    тоесть вставка происходит через N соединений и при этом может откатиться.
    """

    _CACHE_DATA: dict = {}
    _CACHE_LAST_TIME: dict = {}

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

    # CRUD
    async def delete(self, id=None):
        stmt, values = await self.build_delete()
        func_prepare = None
        func_cur = "fetchall"
        async with self._transaction() as tr:
            return await tr.session.execute(stmt, values, func_prepare, func_cur)

    async def update(self, payload: Self | None = None, fields=[]):
        if not payload:
            payload = self
        stmt, values = await self.build_update(payload, fields)
        func_prepare = None
        func_cur = "fetchall"
        async with self._transaction() as tr:
            return await tr.session.execute(stmt, values, func_prepare, func_cur)

    @classmethod
    async def get(cls, id, fields=[]):
        stmt, values = await cls.build_get(id, fields)
        func_prepare = cls.prepare_id
        func_cur = "fetchall"
        async with cls._transaction() as tr:
            record = await tr.session.execute(stmt, values, func_prepare, func_cur)
            assert record is not None
            # record = records[0]
            assert isinstance(record, cls)
            return record

    @classmethod
    async def create(cls, payload):
        stmt, values = await cls.build_create(payload)
        func_prepare = None
        func_cur = "lastrowid"
        if cls._transaction == TransactionPostgresDotORM:
            stmt += " RETURNING id"
        async with cls._transaction() as tr:
            record = await tr.session.execute(stmt, values, func_prepare, func_cur)
            assert record is not None
            if cls._transaction == TransactionPostgresDotORM:
                return record[0]["id"]
            return record
        # TODO: создание relations полей

    @classmethod
    async def search(
        cls,
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
        async with cls._transaction() as tr:
            records = await tr.session.execute(stmt, values, func_prepare, func_cur)
            assert records is not None
            # if len(records) and not raw:
            #     assert type(records) == list[Self]
            #     return records
            return records

    @classmethod
    async def table_len(cls):
        stmt, values = await cls.build_table_len()
        func_prepare = lambda rows: [r["COUNT(*)"] for r in rows]
        if cls._transaction == TransactionPostgresDotORM:
            func_prepare = lambda rows: [r["count"] for r in rows]
        func_cur = "fetchall"
        async with cls._transaction() as tr:
            records = await tr.session.execute(stmt, values, func_prepare, func_cur)
            assert records is not None
            if len(records):
                return records
            return []

    # RELASHIONSHIP
    @classmethod
    async def get_with_relations(cls, id, fields=[], relation_fields=[]):
        request_list, field_name_list = await cls.build_get_with_relations(
            id, fields, relation_fields
        )
        async with cls._transaction() as tr:
            request_list = [
                tr.session.execute(i[0], i[1], i[2], i[3]) for i in request_list
            ]

            # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
            results: list[cls] = await asyncio.gather(*request_list)

            # добавляем атрибуты к исходному обьекту,
            # получая удобное обращение через дот-нотацию
            record = results.pop(0)
            for field in results:
                setattr(record, field_name_list.pop(0), field)

            return record

    async def update_with_relations(self, payload: Self, fields=[]):
        request_list = await self.build_update_with_relations(payload, fields)
        async with self._transaction() as tr:
            request_list = [
                tr.session.execute(i[0], i[1], i[2], i[3]) for i in request_list
            ]
            # 1 conn
            results = tuple()
            for request in request_list:
                res = await request
                results += tuple(res)
            return results

    async def update_one2one(self, fk_id, fields=[], fk="id"):
        stmt, values = await self.build_update_one2one(fk_id, fields, fk)
        func_prepare = None
        func_cur = "fetchall"
        async with self._transaction() as tr:
            res = await tr.session.execute(stmt, values, func_prepare, func_cur)
        return res

    # TODO: universal
    @classmethod
    async def get_many2many(cls, id, comodel, relation, column1, column2, fields=[]):
        stmt, values = await cls.build_get_many2many(
            id, comodel, relation, column1, column2, fields
        )
        func_prepare = comodel.prepare_ids
        func_cur = "fetchall"
        async with cls._transaction() as tr:
            res = await tr.session.execute(stmt, values, func_prepare, func_cur)
        return res

    @classmethod
    async def create_with_relations(cls, payload=None):
        request_list = await cls.build_create_with_relations(payload)
        async with cls._transaction() as tr:
            request_list = [
                tr.session.execute(i[0], i[1], i[2], i[3]) for i in request_list
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
    async def __create_table__(cls):
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
        async with cls._transaction() as tr:
            res = await tr.session.execute(create_table_sql)
        return res
