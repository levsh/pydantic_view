import importlib.metadata

from packaging.version import Version
from packaging.version import parse as version_parse

if version_parse(importlib.metadata.version("pydantic")) < Version("2.0.0"):
    from .v1 import reapply_base_views, view, view_root_validator, view_validator  # noqa
else:
    from .v2 import reapply_base_views, view, view_field_validator, view_model_validator  # noqa


__version__ = importlib.metadata.version("pydantic_view")
