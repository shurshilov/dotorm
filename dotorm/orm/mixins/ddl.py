"""DDL Mixin - provides table creation functionality."""

import datetime
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol

    _Base = DotModelProtocol
else:
    _Base = object

from ...fields import AttachmentMany2one, Field, Many2many, Many2one


class DDLMixin(_Base):
    """
    Mixin providing DDL (Data Definition Language) operations.

    Provides:
    - __create_table__ - creates table based on model fields
    - format_default_value - formats default values for SQL
    - cache decorator for simple TTL caching

    Expects DotModel to provide:
    - _get_db_session()
    - __table__
    - get_fields()
    """

    _CACHE_DATA: ClassVar[dict] = {}
    _CACHE_LAST_TIME: ClassVar[dict] = {}

    @staticmethod
    def cache(name, ttl=30):
        """Реализация простого кеша на TTL секунд, таблиц которые редко меняются,
        и делать запрос в БД не целесообразно каждый раз, можно сохранить результат.
        При использовании более одного воркера необходимо использовать redis.

        Arguments:
            name -- name cache store data
            ttl -- seconds cache store
        """

        def decorator(func):
            async def wrapper(self, *args):
                # если данные есть в кеше
                if self._CACHE_DATA.get(name):
                    time_diff = (
                        datetime.datetime.now() - self._CACHE_LAST_TIME[name]
                    )
                    # проверить актуальные ли они
                    if time_diff.seconds < ttl:
                        # если актуальные вернуть их
                        return self._CACHE_DATA[name]

                # если данных нет или они не актуальные сделать запрос в БД и запомнить
                self._CACHE_DATA[name] = await func(self, *args)
                # также сохранить дату и время запроса, для последующей проверки
                self._CACHE_LAST_TIME[name] = datetime.datetime.now()
                return self._CACHE_DATA[name]

            return wrapper

        return decorator

    @staticmethod
    def format_default_value(value):
        """
        PostgreSQL не поддерживает параметры в DDL, см. официальную документацию:
        Prepared statements are supported only for DML commands
        (SELECT, INSERT, UPDATE, DELETE), not for DDL like CREATE TABLE.
        Поэтому вынуждены делать подстановку вручную в DDL —
        но делать это нужно аккуратно и безопасно.
        """
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        elif isinstance(value, int):
            return str(value)  # int, long

        elif isinstance(value, float):
            # Строгий контроль, чтобы исключить NaN и Inf (они могут вызвать ошибки в SQL)
            if not (value == value and abs(value) != float("inf")):
                raise ValueError("Invalid float for DEFAULT value")
            return str(value)

        elif isinstance(value, str):
            # Явно запрещаем строки с опасными SQL символами
            if ";" in value or "--" in value:
                raise ValueError(
                    "Potentially unsafe characters in default string"
                )
            # SQL-экранирование одинарных кавычек
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        else:
            raise TypeError(
                f"Unsupported type for SQL DEFAULT: {type(value).__name__}"
            )

    @classmethod
    async def __create_table__(cls, session=None):
        """Метод для создания таблицы в базе данных, основанной на атрибутах класса."""
        if session is None:
            session = cls._get_db_session()

        # описание поля для создания в бд со всеми аттрибутами
        fields_created_declaration: list[str] = []
        # только текстовые названия полей
        fields_created: list = []
        # готовый запрос на добавления FK
        many2one_fields_fk: list[str] = []
        many2many_fields_fk: list[str] = []

        # Проходимся по атрибутам класса и извлекаем информацию о полях.
        for field_name, field in cls.get_fields().items():
            if isinstance(field, Field):
                if (field.store and not field.relation) or isinstance(
                    field, (Many2one, AttachmentMany2one)
                ):
                    # Создаём строку с определением поля и добавляем её в список custom_fields.
                    field_declaration = [f'"{field_name}" {field.sql_type}']

                    # SERIAL уже подразумевает NOT NULL, а PRIMARY KEY включает в себя UNIQUE.
                    # Поэтому достаточно просто id SERIAL PRIMARY KEY.
                    if field.unique:
                        field_declaration.append("UNIQUE")
                    if not field.null:
                        field_declaration.append("NOT NULL")
                    if field.primary_key:
                        field_declaration.append("PRIMARY KEY")
                    if field.default is not None:
                        if isinstance(field.default, (bool, int, str)):
                            field_declaration.append(
                                f"DEFAULT {cls.format_default_value(field.default)}"
                            )

                    if isinstance(field, Many2one):
                        # не забыть создать FK для many2one
                        # ALTER TABLE %s ADD FOREIGN KEY (%s) REFERENCES %s(%s) ON DELETE %s",
                        many2one_fields_fk.append(
                            f"""ALTER TABLE IF EXISTS {cls.__table__} ADD FOREIGN KEY ({field_name}) REFERENCES "{field.relation_table.__table__}" (id) ON DELETE {field.ondelete}"""
                        )

                    field_declaration_str = " ".join(field_declaration)
                    fields_created_declaration.append(field_declaration_str)
                    fields_created.append([field_name, field_declaration_str])

                # создаем промежуточную таблицу для many2many
                if field.relation and isinstance(field, Many2many):
                    column1 = f'"{field.column1}" INTEGER NOT NULL'
                    column2 = f'"{field.column2}" INTEGER NOT NULL'
                    # COMMENT ON TABLE {field.many2many_table} IS f"RELATION BETWEEN {model._table} AND {comodel._table}";
                    # CREATE INDEX ON {field.many2many_table} ({field.column1}, {field.column2});
                    # PRIMARY KEY({field.column1}, {field.column2})
                    create_table_sql = f"""\
                    CREATE TABLE IF NOT EXISTS {field.many2many_table} (\
                    {', '.join([column1, column2])}\
                    );
                    """
                    many2many_fields_fk.append(
                        f"""ALTER TABLE IF EXISTS "{field.many2many_table}" ADD FOREIGN KEY ({field.column2}) REFERENCES {cls.__table__} (id) ON DELETE {field.ondelete}"""
                    )
                    many2many_fields_fk.append(
                        f"""ALTER TABLE IF EXISTS "{field.many2many_table}" ADD FOREIGN KEY ({field.column1}) REFERENCES "{field.relation_table.__table__}" (id) ON DELETE {field.ondelete}"""
                    )
                    await session.execute(create_table_sql)

        # Создаём SQL-запрос для создания таблицы с определёнными полями.
        create_table_sql = f"""\
CREATE TABLE IF NOT EXISTS {cls.__table__} (\
{', '.join(fields_created_declaration)}\
);"""

        # Выполняем SQL-запрос.
        await session.execute(create_table_sql)
        # если таблицы уже были созданы, но появились новые поля
        # необходимо их добавить
        for field_name, field_declaration in fields_created:
            sql = f"""SELECT column_name FROM information_schema.columns
WHERE table_name='{cls.__table__}' and column_name='{field_name}';"""

            field_exist = await session.execute(sql)
            if field_exist == "SELECT 0":
                await session.execute(
                    f"""ALTER TABLE {cls.__table__} ADD COLUMN {field_declaration};"""
                )
        return many2one_fields_fk + many2many_fields_fk

    # async def __aiter__(self) -> typing.Iterator[Self]:
    #     """ Return an iterator over ``self``. """
    #     recs = await self.search()
    #     for rec in recs:
    #         yield rec
