"""Canonical ratio presets and validation shared by every UI layer."""

import math
import re


# Keep this order as the product-defined order.  The final web/native control
# entry is a custom text field, so this tuple intentionally contains the 13
# named presets only.
RATIO_PRESETS = (
    '1:1', '1:2', '2:1', '2:3', '3:2', '3:4', '4:3',
    '16:6', '9:16', '16:9', '9:18', '18:9', '21:9',
)

_RATIO_PATTERN = re.compile(
    r'^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$'
)


def normalize_ratio(value):
    """Return a canonical ``width:height`` string, or ``None`` if invalid."""
    if not isinstance(value, str):
        return None
    # Accept the separators users commonly enter in Chinese/English layouts.
    # Internally every layer still receives the same canonical ``w:h`` form.
    normalized_value = value.strip().replace('：', ':').replace('／', ':').replace('/', ':')
    match = _RATIO_PATTERN.fullmatch(normalized_value)
    if not match:
        return None
    width, height = (float(part) for part in match.groups())
    if not math.isfinite(width) or not math.isfinite(height):
        return None
    if width <= 0 or height <= 0 or width > 10000 or height > 10000:
        return None
    return f'{width:g}:{height:g}'


def is_valid_ratio(value):
    """Whether *value* is a positive, bounded ``width:height`` ratio."""
    return normalize_ratio(value) is not None


def ratio_options(current=None):
    """Return presets plus a currently saved custom ratio when necessary."""
    values = list(RATIO_PRESETS)
    normalized = normalize_ratio(current)
    if normalized and normalized not in values:
        values.append(normalized)
    return tuple(values)
