"""Storage port and filesystem adapter (Re-exported from adapters.storage.local)."""

import sys
from jplearn_api.adapters.storage import local as _impl

# Transparently alias to adapters.storage.local so monkeypatching and logger access work identically
sys.modules[__name__] = _impl
