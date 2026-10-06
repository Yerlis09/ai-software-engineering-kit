"""Minimal, non-executing template renderer.

Templates only support ``{{ variable }}`` substitution: no expressions, no code, no
includes. Substitution is single-pass, so user-provided values containing ``{{ }}``
are never expanded again. Unknown variables are an error, which keeps templates honest.
"""

from __future__ import annotations

import re
from typing import Mapping

from ai_project.errors import KitError

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


def render(template: str, values: Mapping[str, str], source: str = "<template>") -> str:
    missing = sorted({m.group(1) for m in _PLACEHOLDER.finditer(template)} - set(values))
    if missing:
        raise KitError(f"Template {source} uses unknown variable(s): {', '.join(missing)}")
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)
