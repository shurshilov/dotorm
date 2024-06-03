import asyncio
from typing import Self, TypeVar


from builder import Builder

from databases.mysql_session import MysqlSessionWithPool

# from model import Model

# T = TypeVar("T", bound=Model)


# class class_or_instancemethod(classmethod):
#     """Этот класс нужен для определения метод вызван в контексте класса или инстанса
#     другими словами @classmethod или @instancemethod
#     """

#     def __get__(self, instance, type_):
#         descr_get = super().__get__ if instance is None else self.__func__.__get__
#         return descr_get(instance, type_)


class DotModel(Builder):
    """Паттерн репозиторий, позволяет не зависить коду от орм/БД.
    только используется не через инверсию зависимостей, а через наследование.
    сессия может передаваться через инверсию зависимостей в случае с работой
    транзакций. Но для паралелльного выполнения вставок в транзакции необходимо удалить FK.
    тоесть вставка происходит через N соединений и при этом может откатиться.
    """

    session_factory = MysqlSessionWithPool

    # CRUD
    # class
    # @class_or_instancemethod
    @classmethod
    async def get(cls, id, fields=[], session=None):
        stmt, values, func_prepare, func_cur = await cls.build_get(id, fields)
        if session:
            record: cls = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            record: cls = await cls.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return record

    # @class_or_instancemethod
    async def delete(self, id=None, session=None):
        stmt, values, func_prepare, func_cur = await self.build_delete()
        if session:
            return await session.execute(stmt, values, func_prepare, func_cur)
        else:
            return await self.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )

    # class
    @classmethod
    async def create(cls, payload, session=None):
        stmt, values, func_prepare, func_cur = await cls.build_create(payload)
        if session:
            record: cls = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            record: cls = await cls.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return record
        # TODO: создание relations полей

    # @class_or_instancemethod
    async def update(self, payload: Self | None = None, fields=[], session=None):
        if not payload:
            payload = self
        stmt, values, func_prepare, func_cur = await self.build_update(payload, fields)
        if session:
            await session.execute(stmt, values, func_prepare, func_cur)
        else:
            return await self.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )

    # class
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
        session=None,
    ) -> list[Self]:
        stmt, values, func_prepare, func_cur = await cls.build_search(
            start, end, limit, order, sort, filter, fields, raw
        )
        if session:
            res = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            res = await cls.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return res

    @classmethod
    async def table_len(cls, session=None):
        stmt, values, func_prepare, func_cur = await cls.build_table_len()
        if session:
            res = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            res = await cls.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return res

    # RELASHIONSHIP
    @classmethod
    async def get_with_relations(cls, id, fields=[], relation_fields=[], session=None):
        request_list, field_name_list = await cls.build_get_with_relations(
            id, fields, relation_fields
        )
        if session:
            request_list = [
                session.execute(i[0], i[1], i[2], i[3]) for i in request_list
            ]
        else:
            request_list = [
                cls.session_factory.execute(i[0], i[1], i[2], i[3])
                for i in request_list
            ]

        # если один из запросов с ошибкой сразу прекратить выполнение и выкинуть ошибку
        results: list[cls] = await asyncio.gather(*request_list)
        # tasks = [asyncio.create_task(request) for request in request_list]
        # done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        # results = []
        # if pending:
        #     for p in pending:
        #         p.cancel()
        #     raise OrmExecutorFirstTaskException
        # for p in done:
        #     results.append(p.result())

        # results = await asyncio.gather(*request_list)
        # добавляем атрибуты к исходному обьекту,
        # получая удобное обращение через дот-нотацию
        record = results.pop(0)
        for field in results:
            setattr(record, field_name_list.pop(0), field)

        return record

    async def update_with_relations(self, payload: Self, fields=[], session=None):
        # если вызов из инстанса, ане из класса
        # if not isinstance(self_or_cls, type):
        #     id = self_or_cls.id
        #     payload = self_or_cls

        request_list = await self.build_update_with_relations(payload, fields)
        if session:
            request_list = [
                session.execute(i[0], i[1], i[2], i[3]) for i in request_list
            ]
        else:
            request_list = [
                self.session_factory.execute(i[0], i[1], i[2], i[3])
                for i in request_list
            ]
        # 1 conn
        results = tuple()
        for request in request_list:
            res = await request
            results += tuple(res)
        # N conns
        # results = await asyncio.gather(*request_list)
        return results

    async def update_one2one(self, fk_id, fields=[], fk="id", session=None):
        stmt, values, func_prepare, func_cur = await self.build_update_one2one(
            fk_id, fields, fk
        )
        if session:
            res = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            res = await self.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return res

    # TODO: universal
    @classmethod
    async def get_many2many(
        cls, id, comodel, relation, column1, column2, fields=[], session=None
    ):
        stmt, values, func_prepare, func_cur = await cls.build_get_many2many(
            id, comodel, relation, column1, column2, fields
        )
        if session:
            res = await session.execute(stmt, values, func_prepare, func_cur)
        else:
            res = await cls.session_factory.execute(
                stmt, values, func_prepare, func_cur
            )
        return res

    @classmethod
    async def create_with_relations(cls, payload=None, session=None):
        request_list = await cls.build_create_with_relations(payload)
        if session:
            request_list = [
                session.execute(i[0], i[1], i[2], i[3]) for i in request_list
            ]
        else:
            request_list = [
                cls.session_factory.execute(i[0], i[1], i[2], i[3])
                for i in request_list
            ]
        # 1 conn
        results = tuple()
        for request in request_list:
            results += tuple(await request)
        # N conns
        # results = await asyncio.gather(*request_list)
        return results

    # async def create_one2one(cls, fk_id=None, fk="id", session=None):
    #     stmt, values, func_prepare, func_cur = await cls.build_create_one2one(fk_id, fk)
    #     if session:
    #         res = await session.execute(stmt, values, func_prepare, func_cur)
    #     else:
    #         res = await cls.session_factory.execute(stmt, values, func_prepare, func_cur)
    #     return res
