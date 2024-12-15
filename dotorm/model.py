from abc import ABCMeta
from enum import IntEnum
import aiomysql
import asyncpg
from typing import Any, ClassVar, Type, dataclass_transform

from .databases.mysql.session import MysqlSessionWithPool

from .databases.postgres.session import PostgresSessionWithPool

from .fields import Field, Many2many, Many2one, One2many, One2one


class JsonMode(IntEnum):
    FORM = 1
    LIST = 2
    CREATE = 3


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ModelMetaclass(ABCMeta): ...


class Model(metaclass=ModelMetaclass):
    """Class for data storage fro DB.
    And manage this data, CRUD.
    """

    # Here ClassVar is a special class defined by the typing module
    # that indicates to the static type checker that this variable
    # should not be set on instances.

    # class variables (it is intended to be shared by all instances)
    # name of table in database
    __table__: ClassVar[str]
    # path name for route ednpoints CRUD
    __route__: ClassVar[str]
    # create CRUD endpoints automaticaly or not
    __auto_crud__: ClassVar[bool] = False
    # name databse
    __database__: ClassVar[str]
    # pool of connections to database
    # use for default usage in orm (without explicit set)
    _pool: ClassVar[aiomysql.Pool | asyncpg.Pool]
    # class that implement no transaction execute
    # single connection -> execute -> release connection to pool
    # use for default usage in orm (without explicit set)
    _no_transaction: ClassVar[Type[PostgresSessionWithPool | MysqlSessionWithPool]]
    # base validation schema for routers endpoints
    __schema__: ClassVar[Type]
    # variables for override auto created - update and create schemas
    __schema_create__: ClassVar[Type]
    __schema_read_output__: ClassVar[Type]
    __schema_read_search_output__: ClassVar[Type]
    __schema_read_search_input__: ClassVar[Type]
    __schema_update__: ClassVar[Type]
    __response_model_exclude__: ClassVar[set[str] | None] = None
    # its auto
    # __schema_output_search__: ClassVar[Type]

    # id required field in any model
    id: ClassVar[int]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # for attr in dir(Message):
        #     if isinstance(getattr(self, attr), Field):
        #         self.fields.append(getattr(self, attr))

        # задаем переменные переданные с помощью args
        # fields = self.get_fields()
        # for i, value in enumerate(args):
        #     setattr(
        #         self, fields[i], value
        #     )
        # if not self.__class__.__schema_create__:
        #     self.__class__.__schema_create__ = self.__class__.__schema__
        # if not self.__class__.__schema_update__:
        #     self.__class__.__schema_update__ = self.__class__.__schema__
        # задаем переменные переданные с помощью kwargs
        # instance variables (it is intended to be used by one instance)
        for name, value in kwargs.items():
            setattr(self, name, value)

    @classmethod
    def _get_db_session(cls):
        return cls._no_transaction(cls._pool)  # type: ignore

    @classmethod
    def prepare_form_ids(cls, rows: list[dict]):
        """Десериализация из списка соварей в список обьектов.
        Используется при получении данных из БД"""
        records = [cls.prepare_form_id([r]) for r in rows]
        return records

    @classmethod
    def prepare_form_id(cls, r: list):
        """Десериализация из словаря в обьект.
        Используется при получении данных из БД"""
        if len(r) != 1:
            raise

        record = cls(**r[0])
        # record_fields = cls(**r[0]).json(exclude_unset=True, mode=JsonMode.FORM)
        # relation_fields = [
        #     (name, field)
        #     for name, field in cls.get_relation_fields()
        #     if name in record_fields.keys()
        # ]
        # for name, field_class in relation_fields:
        #     # если поле many2one или one2one то создаем инстанс модели
        #     if isinstance(field_class, (Many2one, One2one)):
        #         field_instance = getattr(record, name)
        #         # field_instance = record[name]
        #         # только если поле бы реально считано
        #         if not isinstance(field_instance, (Many2one, One2one)):
        #             field_instance = field_class.relation_table.prepare_form_id(
        #                 field_instance
        #             )

        #     # если поле many2many или one2nay то создаем список инстансов модели
        #     elif isinstance(field_class, (Many2many, One2many)):
        #         field_values = []
        #         field_instance = getattr(record, name)
        #         # field_instance = record[name]
        #         # только если поле бы реально считано
        #         if not isinstance(field_instance, (Many2many, One2many)):
        #             for field_row in field_instance:
        #                 field_values.append(
        #                     field_class.relation_table.prepare_form_id(field_row)
        #                 )
        #             field_instance = field_values
        return record

    @classmethod
    def prepare_list_ids(cls, rows: list[dict]):
        """Десериализация из списка соварей в список обьектов.
        Используется при получении данных из БД"""
        return [cls(**r) for r in rows]

    @classmethod
    def prepare_list_id(cls, r: list):
        """Десериализация из словаря в обьект.
        Используется при получении данных из БД.
        Заменяет m2o с обьекта Model на {id:Model}
        Заменяет m2m и o2m с списка Model на list[{id:Model}]
        """
        if len(r) != 1:
            raise

        record = cls(**r[0])
        # for name, field_class in record.get_relation_fields():
        #     # если поле many2one или one2one то создаем инстанс модели
        #     if isinstance(field_class, (Many2one, One2one)):
        #         field_instance = getattr(record, name)
        #         field_instance = {"id": field_instance}

        #     # если поле many2many или one2nay то создаем список инстансов модели
        #     elif isinstance(field_class, (Many2many, One2many)):
        #         field_values = []
        #         field_instance = getattr(record, name)
        #         for field_row in field_instance:
        #             field_values.append({"id": field_row})
        #         field_instance = field_values
        return record

    @classmethod
    def get_fields(cls) -> dict[str, Field]:
        """Основная функция, которая возвращает все поля модели."""
        return {
            attr_name: attr
            for attr_name, attr in cls.__dict__.items()
            # if not callable(v) and not k.startswith("_")
            if isinstance(attr, Field)
        }
        # return {
        #     # cls.__dict__[field_name]
        #     field_name: getattr(cls, field_name)
        #     for field_name, annotation in cls.__annotations__.items()
        # }

    @classmethod
    def get_relation_fields(cls):
        """Только те поля, которые имеют связи. Ассоциации."""
        return [
            (name, field) for name, field in cls.get_fields().items() if field.relation
        ]

    @classmethod
    def get_relation_fields_m2m(cls):
        """Только те поля, которые имеют связи. Ассоциации."""
        return {
            name: field
            for name, field in cls.get_fields().items()
            if field.relation and isinstance(field, Many2many)
        }

    @classmethod
    def get_relation_fields_m2m_o2m(cls):
        """Только те поля, которые имеют связи. Ассоциации."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if field.relation and isinstance(field, (Many2many, One2many))
        ]

    @classmethod
    def get_store_fields(cls) -> list[str]:
        """Возвращает только те поля, которые хранятся в БД.
        Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many
        """
        return [name for name, field in cls.get_fields().items() if field.store]

    @classmethod
    def get_store_fields_dict(cls) -> dict[str, Field]:
        """Возвращает только те поля, которые хранятся в БД.
        Результат в виде dict"""
        return {name: field for name, field in cls.get_fields().items() if field.store}

    @classmethod
    def get_default_values(
        cls, fields_client_nested: dict[str, list[str]]
    ) -> dict[str, Field]:
        """Возвращает поля с установленным значением по умолчанию.
        Используется при создании записи на фронтенде, например
        мы создаем пользователя поле active у которого по умолчанию True.
        """
        default_values = {}
        for name, field in cls.get_fields().items():
            if field.default != None:
                default_values.update({name: field.default})
            elif isinstance(field, (One2many, Many2many)):
                if name in fields_client_nested:
                    fields_client = fields_client_nested[name]
                    fields_info = field.relation_table.get_fields_info_list(
                        fields_client
                    )
                    x2m_default = {
                        "data": [],
                        "fields": fields_info,
                        "total": 0,
                    }
                    default_values.update({name: x2m_default})
        return default_values
        # return {
        #     name: field.default
        #     for name, field in cls.get_fields().items()
        #     if field.default != None
        # }

    @classmethod
    def get_none_update_fields_set(cls) -> set[str]:
        """Возвращает только те поля, которые не используются при обновлении.
        1. Являются primary key (обычно id). (нельзя обновить ид)
        2. Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many.
        (нельзя обновить в БД то чего там нет)
        3. Все relation поля, кроме many2one (так как это просто число, ид)
        (нельзя обновить в БД то чего там нет, one2many)
        """
        return {
            name
            for name, field in cls.get_fields().items()
            if not field.store
            or field.primary_key
            or (field.relation and not isinstance(field, Many2one))
        }

    # def get_store_fields_json(self):
    #     """Возвращает только те поля, которые хранятся в БД.
    #     Для экземпляра класса. В экземпляре поля (класс Field)
    #     преобразуются в реальные данные например Integer -> int"""
    #     store_fields = {}
    #     for field_name, annotation in self.get_store_fields_dict().items():
    #         field = getattr(self, field_name)
    #         if isinstance(field, Field):
    #             store_fields[field_name] = field.default
    #         elif isinstance(field, Model):
    #             store_fields[field_name] = field.id
    #             # store_fields[field_name] = {"id": field.id}
    #         elif isinstance(field, list):
    #             store_fields[field_name] = [rec.id for rec in field]
    #         else:
    #             store_fields[field_name] = field
    #     return store_fields

    @classmethod
    def get_fields_info_list(cls, fields_list: list[str]):
        return [
            {
                "name": name,
                "type": field.__class__.__name__,
                "relation": (
                    field.relation_table.__table__ if field.relation_table else ""
                ),
            }
            for name, field in cls.get_fields().items()
            if name in fields_list
        ]

    @classmethod
    def get_fields_info_form(cls, fields_list: list[str]):
        fields_info = []
        for name, field in cls.get_fields().items():
            if name in fields_list:
                if field.relation:
                    fields_info.append(
                        {
                            "name": name,
                            "type": field.__class__.__name__,
                            "relatedModel": (
                                field.relation_table.__table__
                                if field.relation_table
                                else ""
                            ),
                            "relatedField": (
                                field.relation_table_field
                                if field.relation_table_field
                                else ""
                            ),
                        }
                    )
                else:
                    fields_info.append({"name": name, "type": field.__class__.__name__})
        return fields_info

    def get_json(self, exclude_unset=False, only_store=None, mode=JsonMode.LIST):
        """Возвращает все поля модели.
        Для экземпляра класса. В экземпляре поля (класс Field)
        преобразуются в реальные данные например Integer -> int"""
        fields_json = {}
        if only_store:
            fields = self.get_store_fields_dict().items()
        else:
            fields = self.get_fields().items()

        for field_name, field_class in fields:
            field = getattr(self, field_name)

            # НЕ ЗАДАНО
            # если поле экземпляра класса, осталось классом Field
            # это значит что оно не было считано из БД
            if isinstance(field, Field):
                # если установлен флаг исключить не заланные то ничего не делаем
                if not exclude_unset:
                    if not field.default is None:
                        fields_json[field_name] = field.default
                    else:
                        fields_json[field_name] = None

            # ЗАДАНО как many2one или one2one
            # если поле является моделью то...
            elif isinstance(field, Model):
                if mode == JsonMode.LIST:
                    # обрубаем, исключаем все релейшен поля
                    fields_json[field_name] = {
                        "id": field.id,
                        "name": getattr(field, "name", str(field.id)),
                    }
                elif mode == JsonMode.FORM:
                    fields_json[field_name] = field.json()
                elif mode == JsonMode.CREATE:
                    fields_json[field_name] = field.id

            # ЗАДАНО как many2many или one2many
            elif isinstance(field_class, (Many2many, One2many)):
                if mode == JsonMode.LIST:
                    fields_json[field_name] = [
                        {
                            "id": rec.id,
                            "name": rec.name or str(rec.id),
                        }
                        for rec in field
                    ]
                elif mode == JsonMode.FORM:
                    # TODO: тут надо оставить только те поля которые есть в текущий момент
                    # fields_info = field_class.relation_table.get_fields_info_all()
                    fields_json[field_name] = {
                        "data": [rec.json() for rec in field["data"]],
                        "fields": field["fields"],
                        "total": field["total"],
                    }
                # elif mode == JsonMode.CREATE:
                #     fields_json[field_name] = [{"id": rec.id} for rec in field]

            # ЗАДАНО как значение (число строка время...)
            # иначе поле считается прочитанным из БД и просто пробрасывается
            else:
                fields_json[field_name] = field
        return fields_json

    def json(
        self,
        include={},
        exclude={},
        exclude_none=False,
        exclude_unset=False,
        only_store=None,
        mode=JsonMode.LIST,
    ):
        """Сериализация экземпляра модели в dict python.

        Keyword Arguments:
            include -- только эти поля
            exclude -- исключить поля
            exclude_none -- исключить поля со значением None
            only_store -- только те поля, которые храняться в БД

        Returns:
            python dict
        """
        record = self.get_json(exclude_unset, only_store, mode)
        if include:
            record = {k: v for k, v in record.items() if k in include}
        if exclude:
            record = {k: v for k, v in record.items() if not k in exclude}
        if exclude_none:
            record = {k: v for k, v in record.items() if v is not None}
        # if exclude_unset:
        #     record = {k: v for k, v in record.items() if not isinstance(v, Field)}
        return record
