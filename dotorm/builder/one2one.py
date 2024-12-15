from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..orm import DotModel
from ..model import Model
from .helpers import build_sql_create_from_schema, build_sql_update_from_schema


class BuilderOne2one(Model):
    # READ
    async def build_get_one2one(
        self, relation_table: "DotModel", relation_table_field, id, fields=[]
    ):
        stmt, values_list = await relation_table.build_search(
            filter=[(relation_table_field, "=", id)], limit=1
        )
        return stmt, values_list

    # UPDATE
    async def build_update_one2one(self, fk_id: int, fields=[], fk="id"):
        stmt = f"UPDATE {self.__table__} SET %s WHERE {fk} = %s"
        stmt, values_list = build_sql_update_from_schema(
            sql=stmt, payload=self, id=fk_id, fields=fields, exclude={fk}
        )
        return stmt, values_list

    # CREATE
    async def build_create_one2one(self, fk_id=id, fk="id"):
        stmt = f"INSERT INTO {self.__table__} (%s) VALUES (%s)"
        # TODO: создание relations полей
        setattr(self, fk, fk_id)
        stmt, values_list = build_sql_create_from_schema(stmt, self)
        return stmt, values_list
