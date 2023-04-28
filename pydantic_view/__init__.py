import importlib.metadata

from .pydantic_view import view, view_validator  # noqa

__version__ = importlib.metadata.version("pydantic_view")
