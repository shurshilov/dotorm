from typing import Any

from ..model import Model
from .helpers import build_sql_create_from_schema, build_sql_update_from_schema


class BuilderCRUD(Model):
    @classmethod
    async def build_get(cls, id, fields=[]):
        if not fields:
            fields = ",".join(f'"{name}"' for name in cls.get_store_fields())
        else:
            fields = ",".join(f'"{name}"' for name in fields)
        stmt = f"SELECT {fields} FROM {cls.__table__} WHERE id = %s LIMIT 1"
        return stmt, [id]

    async def build_delete(self, id):
        stmt = f"DELETE FROM {self.__table__} WHERE id=%s"
        return stmt, [id]

    @classmethod
    async def build_create(cls, payload):
        stmt = f"INSERT INTO {cls.__table__} (%s) VALUES (%s)"
        # TODO: создание relations полей
        stmt, values_list = build_sql_create_from_schema(stmt, payload)
        return stmt, values_list

    async def build_update(self, payload, id, fields=[]):
        stmt = f"UPDATE {self.__table__} SET %s WHERE id = %s"
        # TODO: создание relations полей
        stmt, values_list = build_sql_update_from_schema(stmt, payload, id, fields)
        return stmt, values_list

    @classmethod
    async def build_search(
        cls,
        start=None,
        end=None,
        limit=None,
        order="DESC",
        sort="id",
        filter: Any = None,
        fields=[],
        raw=None,
    ):
        if not fields:
            fields = ",".join(f'"{name}"' for name in cls.get_store_fields())
        else:
            fields = ",".join(f'"{name}"' for name in fields)
        where = ""
        where_values = ()
        if filter:
            # фильтруем только те поля, которые есть в модели
            # для текста like, для списка in, для остальных =
            fields_store = cls.get_store_fields_dict()
            fields_store_keys = fields_store.keys()

            where_condition = []
            for key, value in filter.items():
                if key in fields_store_keys:
                    # TODO: поддержка всех операций
                    if type(value) == list:
                        # SQL IN
                        list_condition = [str(field) for field in value]
                        query_placeholders = ", ".join(["%s"] * len(list_condition))
                        where_condition.append(f"{key} in (%s)" % query_placeholders)
                        where_values += tuple(list_condition)
                    elif type(fields_store[key]) == str:
                        # SQL LIKE
                        where_condition.append(f"{key} like %s")
                        # экранирующий процент, чтобы добавить один процент в строку,
                        # чтобы поиск был в любой части строки %%
                        where_values += ("%%" + value + "%%",)
                    else:
                        # SQL =
                        where_condition.append(f"{key} = %s")
                        where_values += (value,)
            if where_condition:
                where = "WHERE " + " and ".join(where_condition)

        stmt = f"select {fields} from {cls.__table__} {where} ORDER BY {sort} {order} "

        if end != None and start != None:
            stmt += "LIMIT %s, %s"
            val = (start, end - start)
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
