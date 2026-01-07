"""
DotORM v2
"""

# Fields
from .fields import (
    Field,
    Integer,
    BigInteger,
    SmallInteger,
    Char,
    Selection,
    Text,
    Boolean,
    Decimal,
    Datetime,
    Date,
    Time,
    Float,
    JSONField,
    Binary,
    Many2one,
    One2many,
    Many2many,
    One2one,
    AttachmentMany2one,
    AttachmentOne2many,
)

# Model
from .model import DotModel
from .model import Model, JsonMode, depends

# Components
from .components import (
    Dialect,
    POSTGRES,
    MYSQL,
    FilterParser,
    FilterExpression,
)

# Exceptions
from .exceptions import (
    OrmConfigurationFieldException,
    OrmUpdateEmptyParamsException,
)

__version__ = "2.0.0"

__all__ = [
    # Fields
    "Field",
    "Integer",
    "BigInteger",
    "SmallInteger",
    "Char",
    "Selection",
    "Text",
    "Boolean",
    "Decimal",
    "Datetime",
    "Date",
    "Time",
    "Float",
    "JSONField",
    "Binary",
    "Many2one",
    "One2many",
    "Many2many",
    "One2one",
    "AttachmentMany2one",
    "AttachmentOne2many",
    # Model
    "DotModel",
    "Model",
    "JsonMode",
    "depends",
    # Components
    "Dialect",
    "POSTGRES",
    "MYSQL",
    "FilterParser",
    "FilterExpression",
    # Exceptions
    "OrmConfigurationFieldException",
    "OrmUpdateEmptyParamsException",
]
