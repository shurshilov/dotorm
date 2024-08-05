from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..orm import DotModel
from ..model import Model


class BuilderMany2many(Model):
    # READ
    @classmethod
    async def build_get_many2many(
        cls,
        id: int,
        comodel: "DotModel",
        relation: str,
        column1: str,
        column2: str,
        fields=[],
    ):
        if not fields:
            fields = cls.get_store_fields()

        select_fields = ",".join(f'"{name}"' for name in fields)

        stmt = f"""
        SELECT {select_fields}
        FROM {comodel.__table__} p

        JOIN {relation} pt ON p.id = pt.{column1}
        JOIN {cls.__table__} t ON pt.{column2} = t.id

        WHERE
            t.id = %s
        """
        # ORDER BY {sort} {order}
        return stmt, [id]  # , comodel.prepare_ids, "fetchall"
