import importlib.metadata

from .pydantic_view import reapply_base_views, view, view_root_validator, view_validator  # noqa

__version__ = importlib.metadata.version("pydantic_view")
