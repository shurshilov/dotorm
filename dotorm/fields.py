"""ORM field definitions."""

import datetime
from decimal import Decimal as PythonDecimal
import logging
from typing import TYPE_CHECKING, Any, Callable, Type

if TYPE_CHECKING:
    from .model import DotModel


log = logging.getLogger("dotorm")
from .exceptions import OrmConfigurationFieldException


class Field[FieldType]:
    """
    Base field class.

    Attributes:
        sql_type - DB field type
        indexable - Can the field be indexed?
        store - Is the field stored in DB? (False for computed/virtual)
        required - Analog of null but reversed

        index - Create index in database?
        primary_key - Is the field primary key?
        null - Is the column nullable?
        unique - Is the field unique?
        description - Field description
        default - Default value
        options - List options for selection field

        relation - Is this a relation field?
        relation_table - Related model class
        relation_table_field - Field name in related model
    """

    # DB attributes
    index: bool = False
    primary_key: bool = False
    null: bool = True
    unique: bool = False
    description: str | None = None
    ondelete: str = "set null"

    # ORM attributes
    required: bool | None = None
    sql_type: str
    indexable: bool = True
    store: bool = True
    default: FieldType | None = None

    string: str = ""
    options: list[str] | None = None
    compute: Callable | None = None
    # compute_deps: Set[str]
    # is_computed: bool = False
    relation: bool = False
    relation_table_field: str | None = None
    # наверное перенести в класс relation
    _relation_table: "DotModel | None" = None

    def __init__(self, **kwargs: Any) -> None:
        # добавляем поле required для удобства работы
        # которое переопределяет null
        self.required = kwargs.pop("required", None)
        if self.required is not None:
            if self.required:
                self.null = False
            else:
                self.null = True

        # self.compute_deps: Set[str] = kwargs.pop("compute_deps", set())
        self.indexable = kwargs.pop("indexable", self.indexable)
        self.store = kwargs.pop("store", self.store)
        # self.primary_key = kwargs.pop("primary_key", False)
        # self.null = kwargs.pop("null", True)
        # self.unique = kwargs.pop("unique", False)
        # self.description = kwargs.pop("description", None)
        # self.default = kwargs.pop("default", None)
        # self.ondelete = "restrict" if self.required else "set null"
        # self.ondelete = kwargs.pop("null", self.null)
        self.ondelete = (
            "set null" if kwargs.pop("null", self.null) else "restrict"
        )

        for name, value in kwargs.items():
            setattr(self, name, value)
        self.validation()

    # обман тайп чекера.
    # TODO: В идеале, сделать так чтобы тип поля менялся если это инстанс или если это класс.
    # 1. Возможно это необходимо сделать в классе скорей всего модели
    # 2. Или перейти на pep-0593 (Integer = Annotated[int, Integer(primary_key=True)])
    # но тогда в классе не будет типа Field и мы получим такую же ситуаци но в классе
    def __new__(cls, *args: Any, **kwargs: Any) -> FieldType:
        return super().__new__(cls)

    def validation(self):
        if not self.indexable and (self.unique or self.index):
            raise OrmConfigurationFieldException(
                f"{self.__class__.__name__} can't be indexed"
            )

        if self.primary_key:
            # UNIQUE or PRIMARY KEY constraint to prevent duplicate values
            self.unique = True

            if self.sql_type == "INTEGER":
                self.sql_type = "SERIAL"
            elif self.sql_type == "BIGINT":
                self.sql_type = "BIGSERIAL"
            elif self.sql_type == "SMALLINT":
                self.sql_type = "SMALLSERIAL"
            else:
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} primary_key supported only for integer, bigint, smallint fields"
                )

            if not self.store:
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} primary_key required store db"
                )
            if self.null:
                log.debug(
                    f"{self.__class__.__name__} can't be both null=True and primary_key=True. Null will be ignored."
                )
                self.null = False
            if self.index:
                # self.index = False
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both index=True and primary_key=True. Primary key have index already."
                )
            # первичный ключ уже автоинкрементируется как SERIAL и имеет значение по умолчанию
            # DEFAULT nextval('tablename_colname_seq')
            if self.default:
                # self.default = None
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both default=True and primary_key=True. Primary key autoincrement already."
                )

        if self.unique:
            if self.index:
                # self.index = False
                raise OrmConfigurationFieldException(
                    f"{self.__class__.__name__} can't be both index=True and unique=True. Index will be ignored."
                )

    @property
    def relation_table(self) -> "DotModel | None":
        # если модель задана через лямбда функцию
        if (
            self._relation_table
            and not isinstance(self._relation_table, type)
            and callable(self._relation_table)
        ):
            return self._relation_table()
        # если модель задана классом
        return self._relation_table

    @relation_table.setter
    def relation_table(self, table):
        self._relation_table = table


class Integer(Field[int]):
    """Integer field (32-bit signed)."""

    field_type = int
    sql_type = "INTEGER"


class BigInteger(Field[int]):
    """Big integer field (64-bit signed)."""

    sql_type = "BIGINT"


class SmallInteger(Field[int]):
    """Small integer field (16-bit signed)."""

    sql_type = "SMALLINT"


class Char(Field[str]):
    """Character field with optional max_length."""

    field_type = str

    def __init__(self, max_length: int | None = None, **kwargs: Any) -> None:
        if max_length:
            if not isinstance(max_length, int):
                raise OrmConfigurationFieldException(
                    "'max_length' should be int, got %s" % type(max_length)
                )
            if max_length < 1:
                raise OrmConfigurationFieldException(
                    "'max_length' must be >= 1"
                )
        self.max_length = max_length
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:
        if self.max_length:
            return f"VARCHAR({self.max_length})"
        return "VARCHAR"


class Selection(Char): ...


class Text(Field[str]):
    """Large text field."""

    field_type = str
    indexable = False
    sql_type = "TEXT"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.unique:
            raise OrmConfigurationFieldException(
                "TextField doesn't support unique indexes, consider CharField or another strategy"
            )
        if self.index:
            raise OrmConfigurationFieldException(
                "TextField can't be indexed, consider CharField"
            )

    class _db_mysql:
        sql_type = "LONGTEXT"


class Boolean(Field[bool]):
    """Boolean field."""

    field_type = bool
    sql_type = "BOOL"


class Decimal(Field[PythonDecimal]):
    """Accurate decimal field."""

    def __init__(
        self, max_digits: int, decimal_places: int, **kwargs: Any
    ) -> None:
        if int(max_digits) < 1:
            raise OrmConfigurationFieldException("'max_digits' must be >= 1")
        if int(decimal_places) < 0:
            raise OrmConfigurationFieldException(
                "'decimal_places' must be >= 0"
            )

        self.max_digits = int(max_digits)
        self.decimal_places = int(decimal_places)
        super().__init__(**kwargs)

    @property
    def sql_type(self) -> str:
        return f"DECIMAL({self.max_digits},{self.decimal_places})"


class Datetime(Field[datetime.datetime]):
    """Datetime field."""

    sql_type = "TIMESTAMPTZ"

    class _db_mysql:
        sql_type = "DATETIME(6)"

    class _db_postgres:
        sql_type = "TIMESTAMPTZ"


class Date(Field[datetime.date]):
    """Date field."""

    sql_type = "DATE"


class Time(Field[datetime.time]):
    """Time field."""

    sql_type = "TIME"

    class _db_mysql:
        sql_type = "TIME(6)"

    class _db_postgres:
        sql_type = "TIMETZ"


class Float(Field[float]):
    """Float (double) field."""

    sql_type = "DOUBLE PRECISION"

    class _db_mysql:
        sql_type = "DOUBLE"


class JSONField(Field[dict | list]):
    """JSON field."""

    sql_type = "JSONB"
    indexable = False

    class _db_mysql:
        sql_type = "JSON"


class Binary(Field[bytes]):
    """Binary bytes field."""

    sql_type = "BYTEA"
    indexable = False

    class _db_mysql:
        sql_type = "VARBINARY"


# ==================== RELATION FIELDS ====================


class Many2one[T: "DotModel"](Field[T]):
    """Many-to-one relation field."""

    field_type = Type
    sql_type = "INTEGER"
    relation = True
    relation_table: "DotModel"

    def __init__(self, relation_table: T, **kwargs: Any) -> None:
        self._relation_table = relation_table
        super().__init__(**kwargs)


class AttachmentMany2one[T: "DotModel"](Field[T]):
    """Many-to-one attachment field."""

    field_type = Type
    sql_type = "INTEGER"
    relation = True
    relation_table: "DotModel"

    def __init__(self, relation_table: T, **kwargs: Any) -> None:
        self._relation_table = relation_table
        super().__init__(**kwargs)


class AttachmentOne2many[T: "DotModel"](Field[list[T]]):
    """One-to-many attachment field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: "DotModel"
    relation_table_field: str

    def __init__(
        self,
        relation_table: T,
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)


class Many2many[T: "DotModel"](Field[list[T]]):
    """Many-to-many relation field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: "DotModel"
    many2many_table: str

    def __init__(
        self,
        relation_table: T,
        many2many_table: str,
        column1: str,
        column2: str,
        **kwargs: Any,
    ) -> None:
        self.relation_table = relation_table
        self.many2many_table = many2many_table
        self.column1: str = column1
        self.column2 = column2
        super().__init__(**kwargs)


class One2many[T: "DotModel"](Field[list[T]]):
    """One-to-many relation field."""

    field_type = list[Type]
    store = False
    relation = True
    relation_table: "DotModel"
    relation_table_field: str

    def __init__(
        self,
        relation_table: T,
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)


class One2one[T: "DotModel"](Field[T]):
    """One-to-one relation field."""

    field_type = Type
    store = False
    relation = True
    relation_table: "DotModel"

    def __init__(
        self,
        relation_table: T,
        relation_table_field: str,
        **kwargs: Any,
    ) -> None:
        self._relation_table = relation_table
        self.relation_table_field = relation_table_field
        super().__init__(**kwargs)
