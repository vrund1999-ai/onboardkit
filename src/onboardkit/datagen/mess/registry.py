"""The mess type registry and the fixed execution order."""

from __future__ import annotations

from typing import TypeVar

from onboardkit.datagen.mess.base import MessType

# Order is part of the dataset definition: structural types first, then value types in this order.
CANONICAL_ORDER = ("households", "names", "formats", "balances")

T = TypeVar("T", bound=MessType)


class MessRegistry:
    def __init__(self) -> None:
        self._types: dict[str, MessType] = {}

    def register(self, cls: type[T]) -> type[T]:
        instance = cls()
        if instance.name in self._types:
            raise ValueError(f"mess type {instance.name!r} is already registered")
        self._types[instance.name] = instance
        return cls

    def names(self) -> list[str]:
        return list(self._types)

    def get(self, name: str) -> MessType:
        try:
            return self._types[name]
        except KeyError:
            raise KeyError(f"unknown mess type {name!r}; valid: {sorted(self._types)}") from None

    def ordered(self, names: list[str]) -> list[MessType]:
        """The named types in execution order: structural first, then canonical, then the rest."""
        registered = list(self._types)
        types = [self.get(name) for name in dict.fromkeys(names)]

        def key(item: MessType) -> tuple[bool, int, int]:
            canonical = CANONICAL_ORDER.index(item.name) if item.name in CANONICAL_ORDER else 99
            return (not item.structural, canonical, registered.index(item.name))

        return sorted(types, key=key)


DEFAULT_REGISTRY = MessRegistry()
register = DEFAULT_REGISTRY.register


def get(name: str) -> MessType:
    return DEFAULT_REGISTRY.get(name)
