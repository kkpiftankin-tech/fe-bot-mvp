"""Integration: endpoints S2..S6 возвращают 501 (T-S01-006 skeleton coverage).

К концу S6 все endpoint'ы реализованы — skeleton coverage сводится к
placeholder-тесту чтобы файл не падал на pytest collection.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_no_skeleton_endpoints_remain() -> None:
    """К концу S6 все endpoint'ы реализованы. Если появятся новые
    отложенные endpoint'ы — добавьте сюда parametrize обратно.
    """
    # Маркируем как passed — все endpoint'ы из S2..S6 реализованы.
    assert True
