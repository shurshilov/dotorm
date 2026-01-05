from dataclasses import dataclass
from typing import Any, Callable, Literal
from ..fields import Field, Many2many, Many2one, One2many

operator = Literal[
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
]


FilterTriplet = tuple[str, operator, Any]
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

    def __init__(self, stmt, value, field_name, field, fields=["id", "name"]) -> None:
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
        if isinstance(self.field, (Many2many, One2many, Many2one)):
            return self.field.relation_table.prepare_form_ids
        else:
            return self.field.relation_table.prepare_form_id

    # @function_prepare.setter
    # def function_prepare(self, function_prepare):
    #     self._function_prepare = function_prepare
