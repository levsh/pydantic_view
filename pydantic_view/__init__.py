import importlib.metadata

from .pydantic_view import reapply_base_views, view, view_field_validator, view_model_validator

__version__ = importlib.metadata.version("pydantic_view")
