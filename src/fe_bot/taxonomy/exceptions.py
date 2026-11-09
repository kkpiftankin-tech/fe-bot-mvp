"""Taxonomy exceptions (SETUP-12)."""

from __future__ import annotations


class TaxonomyError(Exception):
    """Base class для taxonomy-исключений."""


class NoActiveTaxonomyVersionError(TaxonomyError):
    """Поднимается, когда в реестре нет активной версии. Обычно — bootstrap
    проблема (seed не загружен)."""
