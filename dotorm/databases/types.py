from typing import TypedDict


class PostgresPoolSettings(TypedDict):
    host: str
    port: int
    user: str
    password: str
    database: str


class ClickhousePoolSettings(TypedDict):
    host: str
    port: int
    user: str
    password: str
    database: str


class MysqlPoolSettings(TypedDict):
    host: str
    port: int
    user: str
    password: str
    db: str
