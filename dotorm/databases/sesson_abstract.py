from abc import ABC, abstractmethod
from typing import Any, Self


class SessionAbstract(ABC):
    @abstractmethod
    async def execute(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="fetch",
    ) -> Any: ...
