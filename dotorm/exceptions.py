""" Exceptions related to api"""


class OrmConfigurationFieldException(Exception):
    """Exception that raised when called api"""


class OrmUpdateEmptyParamsException(Exception):
    """Exception that raised when called api"""


class OrmExecutorException(Exception):
    """Exception that raised when called api"""


class OrmExecutorFirstTaskException(Exception):
    """Exception that raised when called api"""


class MysqlGetConnectionExecuteException(Exception):
    """Exception that raised when mysql query error"""


class MysqlQueryExecuteException(Exception):
    """Exception that raised when mysql query error"""

    def __init__(self, cmd: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd


class MysqlConnectionExecuteException(Exception):
    """Exception that raised when mysql connection query error"""

    def __init__(self, cmd: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd


class PostgresGetConnectionExecuteException(Exception):
    """Exception that raised when Postgres query error"""


class PostgresQueryExecuteException(Exception):
    """Exception that raised when Postgres query error"""

    def __init__(self, cmd: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd


class PostgresConnectionExecuteException(Exception):
    """Exception that raised when Postgres connection query error"""

    def __init__(self, cmd: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmd = cmd
