from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from ..orm import DotModel
from ..model import Model


class BuilderMany2many(Model):
    # READ
    @classmethod
    async def build_get_many2many(
        cls,
        id: int,
        relation_table: "DotModel",
        many2many_table: str,
        column1: str,
        column2: str,
        fields: list[str],
        order: Literal["desc", "asc"] = "desc",
        start: int | None = None,
        end: int | None = None,
        sort: str = "id",
        limit: int | None = 10,
    ):
        if not fields:
            fields = relation_table.get_store_fields()

        # явно указать для sql запроса что эти поля относятся
        # к связанной таблице
        fields = [f"p.{field}" for field in fields]

        fields_select_stmt = ",".join(f"{name}" for name in fields)

        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p

        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {cls.__table__} t ON pt.{column2} = t.id

        WHERE
            t.id = %s
        ORDER BY {sort} {order}
        """

        val = (id,)
        if end != None and start != None:
            stmt += "LIMIT %s OFFSET %s"
            val += (end - start, start)
        elif limit:
            stmt += "LIMIT %s"
            val += (limit,)

        return stmt, val

    @classmethod
    async def build_get_many2many_multiple(
        cls,
        ids: list[int],
        relation_table: "DotModel",
        many2many_table: str,
        column1: str,
        column2: str,
        fields: list[str] = [],
        limit: int = 80,
    ):
        if not fields:
            fields = relation_table.get_store_fields()

        # явно указать для sql запроса что эти поля относятся
        # к связанной таблице
        fields = [f"p.{field}" for field in fields]

        # добавляем ид из таблицы связи для последующего маппинга записей
        # имеется ввиду за один запрос достаются все записи для всех ид
        # а далее в питоне для каждого ид остаются только его
        fields.append(f"pt.{column2} as m2m_id")

        fields_select_stmt = ",".join(f"{name}" for name in fields)
        query_placeholders = ", ".join(["%s"] * len(ids))

        stmt = f"""
        SELECT {fields_select_stmt}
        FROM {relation_table.__table__} p

        JOIN {many2many_table} pt ON p.id = pt.{column1}
        JOIN {cls.__table__} t ON pt.{column2} = t.id

        WHERE
            t.id in ({query_placeholders})
        LIMIT {limit}
        """

        return stmt
