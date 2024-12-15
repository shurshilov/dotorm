from typing import Literal

from .utils import FilterTriplet
from ..model import JsonMode, Model
from .helpers import (
    build_sql_create_from_schema,
    build_sql_update_from_schema,
)


class BuilderCRUD(Model):
    @classmethod
    async def build_get(cls, id, fields=[]):
        if not fields:
            fields = ",".join(f'"{name}"' for name in cls.get_store_fields())
        else:
            fields = ",".join(f'"{name}"' for name in fields)
        stmt = f"SELECT {fields} FROM {cls.__table__} WHERE id = %s LIMIT 1"
        return stmt, [id]

    async def build_delete(self):
        return f"DELETE FROM {self.__table__} WHERE id=%s"

    @classmethod
    async def build_delete_bulk(cls, len: int):
        # # return f"DELETE FROM {cls.__table__} WHERE id = any($1::int[])"
        args: str = ",".join(["%s"] * len)
        return f"DELETE FROM {cls.__table__} WHERE id in ({args})"

    @classmethod
    async def build_create(cls, payload):
        stmt = f"INSERT INTO {cls.__table__} (%s) VALUES (%s)"
        # TODO: создание relations полей
        stmt, values_list = build_sql_create_from_schema(stmt, payload)
        return stmt, values_list

    @classmethod
    async def build_create_bulk(cls, payloads: list[Model]):
        # TODO: создание relations полей
        # только если количесттво полей одинаковое в каждом payload
        values_lists = []

        for payload in payloads:
            payload_no_relation = payload.json(
                # exclude=payload.get_none_update_fields_set(),
                only_store=True,
                mode=JsonMode.CREATE,
            )
            fields_list, values_list = zip(*payload_no_relation.items())
            values_lists.append(values_list)

        # оставляем только поля переданные в запросе
        fields_list = list(
            payload.json(
                exclude=payload.get_none_update_fields_set(),
                exclude_unset=True,
                only_store=True,
                mode=JsonMode.CREATE,
            ).keys()
        )
        query_columns = ", ".join(fields_list)
        query_columns_returning = ", ".join([f"r.{field}" for field in fields_list])
        # query_placeholders = ", ".join(["%s"] * len(values_list))
        # stmt = f"INSERT INTO {cls.__table__} ({query_columns}) VALUES ({query_placeholders})"
        stmt = f"INSERT INTO {cls.__table__} ({query_columns}) "
        return stmt, values_lists, query_columns_returning

    @classmethod
    async def build_update(cls, payload, id, fields=[]):
        stmt = f"UPDATE {cls.__table__} SET %s WHERE id = %s"
        # TODO: создание relations полей
        stmt, values_list = build_sql_update_from_schema(stmt, payload, id, fields)
        return stmt, values_list

    @classmethod
    async def build_update_bulk(cls, payload, ids):
        stmt = f"UPDATE {cls.__table__} SET %s WHERE id in (%s)"
        stmt, values_list = build_sql_update_from_schema(stmt, payload, ids)
        return stmt, values_list

    @classmethod
    async def build_search(
        cls,
        fields: list[str] = ["id"],
        start: int | None = None,
        end: int | None = None,
        limit: int = 80,
        order: Literal["DESC", "ASC", "desc", "asc"] = "DESC",
        sort: str = "id",
        filter: list[FilterTriplet] | None = None,
        raw: bool = False,
    ):
        # SEARCH STORE
        # if not fields:
        #     fields_store_stmt = ",".join(f'"{name}"' for name in cls.get_store_fields())
        # else:
        fields_store_stmt = ",".join(
            f'"{name}"' for name in fields if name in cls.get_store_fields()
        )
        where = ""
        where_values = ()
        where_condition = []
        if filter:
            # TODO: поддержка операций для связей
            # а также между триплетами или и
            for field_triplet in filter:
                name, operator, value = field_triplet
                if operator in ["in", "not in"]:
                    # SQL IN, NOT IN
                    list_condition = [field for field in value]
                    query_placeholders = ", ".join(["%s"] * len(list_condition))
                    where_condition.append(
                        f"{name} {operator} (%s)" % query_placeholders
                    )
                    where_values += tuple(list_condition)
                if operator in [
                    "like",
                    "ilike",
                    "=like",
                    "=ilike",
                    "not ilike",
                    "not like",
                ]:
                    # SQL LIKE ILIKE
                    where_condition.append(f"{name} {operator} %s")
                    # экранирующий процент, чтобы добавить один процент в строку,
                    # чтобы поиск был в любой части строки %%
                    where_values += ("%%" + value + "%%",)
                if operator in ["=", ">", "<", "!=", ">=", "<="]:
                    # SQL "=", ">", "<", "!=", ">=", "<="
                    where_condition.append(f"{name} {operator} %s")
                    where_values += (value,)
            if where_condition:
                where = "WHERE " + " and ".join(where_condition)

        stmt = f"select {fields_store_stmt} from {cls.__table__} {where} ORDER BY {sort} {order} "

        if end != None and start != None:
            stmt += "LIMIT %s OFFSET %s"
            val = (end - start, start)
        elif limit:
            stmt += "LIMIT %s"
            val = (limit,)
        else:
            val = tuple()
        if where_values:
            val = where_values + val

        return stmt, val

    @classmethod
    async def build_table_len(cls):
        stmt = f"SELECT COUNT(*) FROM {cls.__table__}"
        return stmt, None
