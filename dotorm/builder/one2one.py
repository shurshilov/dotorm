from ..exceptions import OrmUpdateEmptyParamsException
from ..model import Model
from .helpers import build_sql_create_from_schema, build_sql_update_from_schema


class BuilderOne2one(Model):
    async def build_update_one2one(self, fk_id: int, fields=[], fk="id"):
        if not fk_id:
            raise OrmUpdateEmptyParamsException

        stmt = f"UPDATE {self.__table__} SET %s WHERE {fk} = %s"
        stmt, values_list = build_sql_update_from_schema(
            sql=stmt, payload=self, id=fk_id, fields=fields, exclude={fk}
        )
        return stmt, values_list

    async def build_create_one2one(self, fk_id=id, fk="id"):
        if not fk_id:
            raise OrmUpdateEmptyParamsException

        stmt = f"INSERT INTO {self.__table__} (%s) VALUES (%s)"
        # TODO: создание relations полей
        setattr(self, fk, fk_id)
        stmt, values_list = build_sql_create_from_schema(stmt, self)
        return stmt, values_list
