from __future__ import annotations

import sys
from pathlib import Path


# Ensure project root is importable (so `import first_page` works).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Importing this module executes the Streamlit app as currently implemented.
# Keep it as-is until we encapsulate the page into a render() function.
import first_page  # noqa: F401