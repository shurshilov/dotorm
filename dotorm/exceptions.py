""" Exceptions related to orm and builder"""


class OrmConfigurationFieldException(Exception):
    """Exception that raised when wrong config model or fields"""


class OrmUpdateEmptyParamsException(Exception):
    """Exception that raised when orm not have required params"""
