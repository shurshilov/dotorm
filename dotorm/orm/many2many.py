import asyncio
from typing import Literal

from .primary import OrmPrimary

from ..builder.primary import BuilderCRUDPrimary


from ..builder.relashions import BuilderCRUDRelashions
from ..fields import Field, Many2many, Many2one, One2many


# BuilderCRUDPrimary, BuilderMany2many
# для build_search_relation наледование от BuilderCRUDRelashions
# class OrmMany2many(BuilderCRUDRelashions):
class OrmMany2many(OrmPrimary, BuilderCRUDRelashions):
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
        fields_store = [name for name in comodel.get_store_fields() if name in fields]
        if not fields_store:
            fields_store = comodel.get_store_fields()
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
    async def _records_list_get_relation(cls, session, fields_relation, records):
        dialect = "postgres"
        if not cls._is_postgres:
            dialect = "mysql"

        request_list = await cls.build_search_relation(
            fields_relation, records, dialect=dialect
        )
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
