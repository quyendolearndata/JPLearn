"""Re-export SQLAlchemy models from adapters layer for backward compatibility."""

from __future__ import annotations

import sys
from jplearn_api.adapters.persistence import models as _impl

sys.modules[__name__] = _impl
