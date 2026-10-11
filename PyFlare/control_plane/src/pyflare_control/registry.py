"""Capability and provider registries with explicit duplicate handling."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Capability, Provider


class RegistryConflictError(ValueError):
    pass


class CapabilityRegistry:
    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._items: dict[str, Capability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability, *, replace: bool = False) -> None:
        if capability.capability_id in self._items and not replace:
            raise RegistryConflictError(
                f"capability already registered: {capability.capability_id}"
            )
        self._items[capability.capability_id] = capability

    def get(self, capability_id: str) -> Capability | None:
        return self._items.get(capability_id)

    def require(self, capability_id: str) -> Capability:
        capability = self.get(capability_id)
        if capability is None:
            raise KeyError(f"unknown capability: {capability_id}")
        return capability

    def ids(self) -> frozenset[str]:
        return frozenset(self._items)


class ProviderRegistry:
    def __init__(self, providers: Iterable[Provider] = ()) -> None:
        self._items: dict[str, Provider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: Provider, *, replace: bool = False) -> None:
        if provider.provider_id in self._items and not replace:
            raise RegistryConflictError(f"provider already registered: {provider.provider_id}")
        self._items[provider.provider_id] = provider

    def get(self, provider_id: str) -> Provider | None:
        return self._items.get(provider_id)

    def all(self) -> tuple[Provider, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
