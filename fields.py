import datetime
from typing import Any, Type, TypeVar
from decimal import Decimal

T = TypeVar("T")


class Field[FieldType]:
    # __slots__ = ('python_type',
    #             'pydantic_type',
    #             'store',
    #             'default'
    #             )
    relation = False
    relation_table = None
    relation_table_field = None
    primary_key = False
    store = True
    indexable = True

    def __init__(self, **kwargs: Any) -> None:
        self.python_type: type = kwargs.pop("python_type", None)
        self.pydantic_type: type = kwargs.pop("pydantic_type", None)
        self.store = kwargs.pop("store", True)
        self.default = kwargs.pop("default", None)

        for name, value in kwargs.items():
            setattr(self, name, value)

    def __new__(cls, *args: Any, **kwargs: Any) -> FieldType:
        return super().__new__(cls)


class Integer(Field[int]):
    """
    Integer field. (32-bit signed)

    ``primary_key`` (bool):
        True if field is Primary Key.
    """

    field_type = int
    sql_type = "INT"

    class _db_postgres:
        GENERATED_SQL = "SERIAL NOT NULL PRIMARY KEY"

    class _db_mysql:
        GENERATED_SQL = "INT NOT NULL PRIMARY KEY AUTO_INCREMENT"


class BigInteger(Field[int]):
    """
    Big integer field. (64-bit signed)

    ``primary_key`` (bool):
        True if field is Primary Key.
    """

    sql_type = "BIGINT"

    class _db_postgres:
        GENERATED_SQL = "BIGSERIAL NOT NULL PRIMARY KEY"

    class _db_mysql:
        GENERATED_SQL = "BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT"


class SmallInteger(Field[int]):
    """
    Small integer field. (16-bit signed)

    ``primary_key`` (bool):
        True if field is Primary Key.
    """

    sql_type = "SMALLINT"

    class _db_postgres:
        GENERATED_SQL = "SMALLSERIAL NOT NULL PRIMARY KEY"

    class _db_mysql:
        GENERATED_SQL = "SMALLINT NOT NULL PRIMARY KEY AUTO_INCREMENT"


class Char(Field[str]):
    """
    Character field.

    You must provide the following:

    ``max_length`` (int):
        Maximum length of the field in characters.
    """

    field_type = str

    def __init__(self, max_length: int, **kwargs: Any) -> None:
        self.max_length = int(max_length)
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"


class Text(Field[str]):  # type: ignore
    """
    Large Text field.
    """

    field_type = str
    indexable = False
    sql_type = "TEXT"

    class _db_mysql:
        sql_type = "LONGTEXT"


class Boolean(Field[bool]):
    """
    Boolean field.
    """

    field_type = bool
    sql_type = "BOOL"


class Decimal(Field[Decimal]):
    """
    Accurate decimal field.

    You must provide the following:

    """

    def __init__(self, max_digits: int, decimal_places: int, **kwargs: Any) -> None:
        self.max_digits = int(max_digits)
        self.decimal_places = int(decimal_places)
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:  # type: ignore
        return f"DECIMAL({self.max_digits},{self.decimal_places})"


class Datetime(Field[datetime.datetime]):
    """
    Datetime field.

    """

    sql_type = "TIMESTAMP"

    class _db_mysql:
        sql_type = "DATETIME(6)"

    class _db_postgres:
        sql_type = "TIMESTAMPTZ"


class Date(Field[datetime.date]):
    """
    Date field.
    """

    sql_type = "DATE"


class Time(Field[datetime.time]):
    """
    Time field.
    """

    sql_type = "TIME"

    class _db_mysql:
        sql_type = "TIME(6)"

    class _db_postgres:
        sql_type = "TIMETZ"


class Float(Field[float]):
    """
    Float (double) field.
    """

    sql_type = "DOUBLE PRECISION"

    class _db_mysql:
        sql_type = "DOUBLE"


class JSONField(Field[dict | list]):
    """
    JSON field.

    """

    sql_type = "JSON"
    indexable = False

    class _db_postgres:
        sql_type = "JSONB"


# class Relation: ...


class Many2one(Field[Type[T]]):
    """
    Many2one field.
    """

    field_type = Type
    sql_type = "INT"

    def __init__(self, relation_table: Type, **kwargs: Any) -> None:
        self.relation_table = relation_table
        self.relation = kwargs.get("relation", True)
        super().__init__(**kwargs)


class Many2many(Field[list[T]]):
    """
    Many2many field.
    """

    field_type = list[Type]
    store = False

    def __init__(
        self,
        relation_table: Type,
        many2many_table: str,
        column1: str,
        column2: str,
        **kwargs: Any,
    ) -> None:
        self.relation_table = relation_table
        self.many2many_table = many2many_table
        self.column1 = column1
        self.column2 = column2
        self.relation = kwargs.get("relation", True)
        super().__init__(**kwargs)


class One2many(Field[list[Type[T]]]):
    """
    One2many field.
    """

    field_type = list[Type]
    store = False

    def __init__(
        self,
        relation_table: Type,
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self.relation_table = relation_table
        self.relation_table_field = relation_table_field
        self.relation = kwargs.get("relation", True)
        super().__init__(**kwargs)


class One2one(Field[Type]):
    """
    One2one field.
    """

    field_type = Type
    store = False

    def __init__(
        self,
        relation_table: Type,
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self.relation_table = relation_table
        self.relation_table_field = relation_table_field
        self.relation = kwargs.get("relation", True)
        super().__init__(**kwargs)
