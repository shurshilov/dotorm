from typing import TypedDict


class PoolSettings(TypedDict):
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
