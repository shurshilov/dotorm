"""Abstract session interface."""

from abc import ABC, abstractmethod


class SessionAbstract(ABC):
    @abstractmethod
    async def execute(
        self,
        stmt: str,
        val=None,
        func_prepare=None,
        func_cur="fetch",
    ): ...
