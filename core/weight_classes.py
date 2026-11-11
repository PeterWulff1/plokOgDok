"""Order of vlstat's weight class labels on result pages.

vlstat writes classes as "-81kg", "+109kg" and "-49 kg", with masters and other prefixes
("45-49år -81kg", "Junior -63kg", "U23 (uofficiel) +86kg"), as ranges ("71 - 81kg") or as
"udenfor konkurrence". Sorted as text, "-110kg" lands before "-70kg"."""

import re

_PREFIX = re.compile(r"^(.*\S)\s+[-+]\d+\s*kg$")  # "45-49år -81kg" -> "45-49år"
_LIMIT = re.compile(r"(\d+)\s*kg$")  # the class's kg number, last in the label
_OPEN = re.compile(r"\+\s*\d+\s*kg$")  # "+109kg": the open class above 109


def weight_class_sort_key(label: str | None) -> tuple:
    """Sort key: no class first, then per prefix group (no prefix first) lightest to
    heaviest, the "+" class right after the class with the same number, and labels
    without a kg number ("udenfor konkurrence") last."""
    if label is None:
        return (0,)
    limit = _LIMIT.search(label)
    if limit is None:
        return (2, label)
    prefix = m.group(1) if (m := _PREFIX.match(label)) else ""
    return (1, prefix, int(limit.group(1)), bool(_OPEN.search(label)), label)
