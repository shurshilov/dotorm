try:
    from pydantic import create_model
except:
    print("pydantic lib not installed")
from typing import Literal, Union


from .fields import (
    Many2many,
    One2many,
    Field as DotField,
)


def dotorm_to_pydantic_nested_one(cls):
    """Работает с моделями DotOrm.
    Которая возвращает все поля модели.
    Используется на вход get и create_default
    Прерывается на первом уровне вложенности"""
    fields_store = []
    fields_relation = []
    # fields = []
    for field_name, field in cls.__dict__.items():
        if isinstance(field, DotField):
            if not isinstance(field, (Many2many, One2many)):
                fields_store.append(field_name)

            else:
                # если это поле множественной связи m2m или o2m
                # то это поле будет содержать просто список своих полей
                allowed_fields = list(field.relation_table.get_fields())
                params = {field_name: (list[Literal[*allowed_fields]], ...)}
                SchemaGetFieldRelationInput = create_model(
                    "SchemaGetFieldRelationInput",
                    **params,
                )  # type: ignore
                fields_relation.append(SchemaGetFieldRelationInput)

    return create_model(
        "SchemaGetInput",
        fields=(list[Union[Literal[*fields_store], *fields_relation]], ...),
    )
