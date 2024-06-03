from typing import Optional

from pypika import Table, Query
from datetime import datetime


class TypedTable(Table):
    __table__ = ""

    def __init__(
        self,
        name: Optional[str] = None,
        schema: Optional[str] = None,
        alias: Optional[str] = None,
        query_cls: Optional[Query] = None,
    ) -> None:
        if name is None:
            if self.__table__:
                name = self.__table__
            else:
                name = self.__class__.__name__

        super().__init__(name, schema, alias, query_cls)


class Product(TypedTable):
    __table__ = "core_product"

    id: int
    name: str
    price: int


product_tb = Product()
product_tb.p
