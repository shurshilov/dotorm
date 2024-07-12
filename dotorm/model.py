from abc import ABCMeta
from typing import Any, ClassVar, Type, dataclass_transform

import aiomysql
import asyncpg


from .fields import Field, Many2one


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ModelMetaclass(ABCMeta): ...


class Model(metaclass=ModelMetaclass):
    __table__: ClassVar[str]
    __route__: ClassVar[str]
    __schema__: ClassVar[Type]
    __database__: ClassVar[str]
    _pool: ClassVar[aiomysql.Pool | asyncpg.Pool]
    # __schema_output_read__: ClassVar[Type]
    # __schema_input_create__: ClassVar[Type]
    # __schema_input_update__: ClassVar[Type]

    # _transaction: Type[TransactionPostgresDotORM | TransactionMysqlDotORM] = (
    #     TransactionMysqlDotORM
    # )
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

        # задаем переменные переданные с помощью kwargs
        for name, value in kwargs.items():
            setattr(self, name, value)

    def get_store_fields_instance(self):
        store_fields = {}
        for field_name, annotation in self.get_store_fields_dict().items():
            field = getattr(self, field_name)
            if isinstance(field, Field):
                store_fields[field_name] = field.default
            else:
                store_fields[field_name] = field
        return store_fields

    def get_fields_instance(self):
        fields = {}
        for field_name, annotation in self.get_fields().items():
            field = getattr(self, field_name)
            if isinstance(field, Field):
                fields[field_name] = field.default
            else:
                fields[field_name] = field
        return fields

    def json(self, include={}, exclude={}, exclude_none=False, only_store=None):
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
        """десериализация из списка соварей в обьект"""
        return [cls(**r) for r in rows]

    @classmethod
    def prepare_id(cls, r: dict):
        """десериализация из словаря в обьект"""
        return cls(**r[0])

    # @classmethod
    # def get_field(cls, field_name: str) -> Field:
    #     return getattr(cls, field_name)

    # @classmethod
    # def get_fields_name(cls):
    #     return [field_name for field_name, annotation in cls.__annotations__.items()]

    @classmethod
    def get_fields(cls) -> dict[str, Field]:
        return {
            # cls.__dict__[field_name]
            field_name: getattr(cls, field_name)
            for field_name, annotation in cls.__annotations__.items()
        }

    @classmethod
    def get_relation_fields(cls):
        """Возвращает только те поля, которые имеют связи. Ассоциации."""
        return [
            (name, field)
            for name, field in cls.get_fields().items()
            if isinstance(field, Field) and field.relation
        ]

    @classmethod
    def get_none_update_fields_set(cls):
        """Возвращает только те поля, которые не используются при обновлении.
        1. Являются primary key (обычно id).
        2. Поля, у которых store = False, не хранятся в бд. По умолчанию все поля store = True.
        3. Все relation поля, кроме many2one (так как это просто число, ид)
        """
        return {
            name
            for name, field in cls.get_fields().items()
            if isinstance(field, Field)
            # and not name.startswith("_")
            and (
                not field.store
                or field.primary_key
                or (field.relation and not isinstance(field, Many2one))
                # or field.get("relation", "many2one") != "many2one"
            )
        }

    @classmethod
    def get_store_fields(cls) -> list[str]:
        """Возвращает только те поля, которые хранятся в БД.
        Поля, у которых store = False, не хранятся в бд.
        По умолчанию все поля store = True, кроме One2many и Many2many
        """
        return [
            name
            for name, field in cls.get_fields().items()
            if (isinstance(field, Field) and field.store and not field.relation)
            or (not isinstance(field, Field) and not name.startswith("_"))
        ]

    @classmethod
    def get_store_fields_dict(cls) -> dict[str, Field[Any]]:
        return {
            name: field
            for name, field in cls.get_fields().items()
            if (isinstance(field, Field) and field.store and not field.relation)
            or (not isinstance(field, Field) and not name.startswith("_"))
        }
