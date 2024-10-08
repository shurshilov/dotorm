from abc import ABCMeta
import aiomysql
import asyncpg
from typing import Any, ClassVar, Type, dataclass_transform

from .fields import Field, Many2one


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
    _pool: ClassVar[aiomysql.Pool | asyncpg.Pool]
    # base validation schema for routers endpoints
    __schema__: ClassVar[Type]
    # variables for override auto created - update and create schemas
    __schema_create__: ClassVar[Type]
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

    # def get_fields_instance_filter(self, include={}, exclude={}, exclude_none=False):
    #     fields = self.get_fields_instance()
    #     if include:
    #         fields = {k: v for k, v in fields.items() if k in include}
    #     if exclude:
    #         fields = {k: v for k, v in fields.items() if not k in exclude}
    #     if exclude_none:
    #         fields = {k: v for k, v in fields.items() if v is not None}
    #     return fields

    @classmethod
    def prepare_ids(cls, rows: list[dict]):
        """Десериализация из списка соварей в список обьектов.
        Используется при получении данных из БД"""
        return [cls(**r) for r in rows]

    @classmethod
    def prepare_id(cls, r: dict):
        """Десериализация из словаря в обьект.
        Используется при получении данных из БД"""
        return cls(**r[0])

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
    def get_default_values(cls) -> dict[str, Field]:
        """Возвращает поля с установленным значением по умолчанию.
        Используется при создании записи на фронтенде, например
        мы создаем пользователя поле active у которого по умолчанию True.
        """
        return {
            name: field.default
            for name, field in cls.get_fields().items()
            if field.default != None
        }

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

    def get_store_fields_instance(self):
        """Возвращает только те поля, которые хранятся в БД.
        Для экземпляра класса. В экземпляре поля (класс Field)
        преобразуются в реальные данные например Integer -> int"""
        store_fields = {}
        for field_name, annotation in self.get_store_fields_dict().items():
            field = getattr(self, field_name)
            if isinstance(field, Field):
                store_fields[field_name] = field.default
            elif isinstance(field, Model):
                store_fields[field_name] = field.id
            elif isinstance(field, list):
                store_fields[field_name] = [rec.id for rec in field]
            else:
                store_fields[field_name] = field
        return store_fields

    def get_fields_instance(self):
        """Возвращает все поля модели.
        Для экземпляра класса. В экземпляре поля (класс Field)
        преобразуются в реальные данные например Integer -> int"""
        fields = {}
        for field_name, annotation in self.get_fields().items():
            field = getattr(self, field_name)
            if isinstance(field, Field):
                fields[field_name] = field.default
            elif isinstance(field, Model):
                fields[field_name] = field.id
            elif isinstance(field, list):
                fields[field_name] = [rec.id for rec in field]
            else:
                fields[field_name] = field
        return fields

    def json(self, include={}, exclude={}, exclude_none=False, only_store=None):
        """Сериализация экземпляра модели в dict python.

        Keyword Arguments:
            include -- только эти поля
            exclude -- исключить поля
            exclude_none -- исключить поля со значением None
            only_store -- только те поля, которые храняться в БД

        Returns:
            python dict
        """
        if only_store:
            fields = self.get_store_fields_instance()
        else:
            fields = self.get_fields_instance()
        if include:
            fields = {k: v for k, v in fields.items() if k in include}
        if exclude:
            fields = {k: v for k, v in fields.items() if not k in exclude}
        if exclude_none:
            fields = {k: v for k, v in fields.items() if v is not None}
        return fields
