from __future__ import annotations  # 👈 Это нужно добавить!
from typing import Any, Callable, Literal, Union
from ..fields import (
    AttachmentMany2one,
    AttachmentOne2many,
    Field,
    Many2many,
    Many2one,
    One2many,
)

# Поддерживаемые SQL-операторы
SQLOperator = Literal[
    "=",
    ">",
    "<",
    "!=",
    ">=",
    "<=",
    "like",
    "ilike",
    "=like",
    "=ilike",
    "not ilike",
    "not like",
    "in",
    "not in",
    "is null",
    "is not null",
    "between",
    "not between",
]

# Одинарный фильтр: (поле, оператор, значение)
# FilterTriplet = tuple[str, SQLOperator, Any]

# # Рекурсивный тип фильтра
# FilterExpression = Union[
#     FilterTriplet,
#     tuple[Literal["not"], "FilterExpression"],  # NOT выражение
#     list[
#         Union["FilterExpression", Literal["and", "or"]]
#     ],  # Список выражений с логикой
# ]

# FilterExpression = Annotated[Any]
FilterTriplet = tuple[str, SQLOperator, Any]

FilterExpression = list[
    FilterTriplet
    | tuple[Literal["not"], "FilterExpression"]
    | list[Union["FilterExpression", Literal["and", "or"]]],
]

# @dataclass
# class FilterTriplet[Model]:
#     # allowed_fields = list(self.Model.get_fields())
#     # (list[Literal[*allowed_fields]], ...)
#     name: str
#     operator: operator
#     value: Any


class RequestBuilder:
    stmt: str
    value: Any
    field_name: str
    field: Field
    fields: list
    # function_prepare: Callable
    function_curcor: str = "fetchall"

    def __init__(
        self, stmt, value, field_name, field, fields=["id", "name"]
    ) -> None:
        self.stmt = stmt
        self.value = value
        self.field_name = field_name
        self.field = field
        self.fields = fields

    @property
    def function_prepare(self) -> Callable:
        if isinstance(self.field, (Many2many, One2many, Many2one)):
            return self.field.relation_table.prepare_list_ids
        # TODO: помоему тут ошибка relation_table всегда будет пустое
        # а реквест билдер всеравно не используется в не связей
        # и else никогда не вызывается
        else:
            return self.field.relation_table.prepare_list_id

    @function_prepare.setter
    def function_prepare(self, function_prepare):
        self._function_prepare = function_prepare


class RequestBuilderForm(RequestBuilder):
    @property
    def function_prepare(self) -> Callable:
        if isinstance(
            self.field,
            (
                Many2many,
                One2many,
                Many2one,
                AttachmentMany2one,
                AttachmentOne2many,
            ),
        ):
            return self.field.relation_table.prepare_form_ids
        else:
            return self.field.relation_table.prepare_form_id

    # @function_prepare.setter
    # def function_prepare(self, function_prepare):
    #     self._function_prepare = function_prepare
