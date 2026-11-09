"""Root pytest conftest.

Тесты не должны касаться dev-only JSON snapshot persistence:
- Не хотим, чтобы они писали в var/state/
- Не хотим, чтобы они подтягивали закешированный state с прошлого запуска
"""

from __future__ import annotations

import os

os.environ.setdefault("FE_BOT_DISABLE_PERSISTENCE", "1")
