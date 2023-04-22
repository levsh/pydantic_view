from copy import deepcopy
from typing import Dict, Set, _GenericAlias

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def view(
    name: str,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_ex: Dict[str, FieldInfo] = None,
    recursive: bool = None,
):
    def wrapper(cls):

        include_ = set(cls.__fields__.keys())
        if include is not None:
            include_ &= set(include)

        exclude_ = set()
        if exclude is not None:
            exclude_ = set(exclude)

        if include and exclude and set(include) & set(exclude):
            raise ValueError("include and exclude cannot contain the same fields")

        fields = {k: deepcopy(v) for k, v in cls.__fields__.items() if k in include_ and k not in exclude_}

        if optional:
            for field_name in optional:
                if field_name not in fields:
                    raise Exception(f"View has not field '{field_name}'")
                fields[field_name].required = False

        if optional_ex:
            for field_name, v in optional_ex.items():
                if field_name not in fields:
                    raise Exception(f"View has not field '{field_name}'")
                if not isinstance(v, FieldInfo):
                    raise TypeError("Expect FieldInfo")
                field = fields[field_name]
                field.required = False
                field.field_info = v
                field.default = v.default
                field.default_factory = v.default_factory

        if recursive is True:

            def update_type(tp):
                if isinstance(tp, _GenericAlias):
                    tp.__args__ = tuple(update_type(arg) for arg in tp.__args__)
                elif issubclass(tp, BaseModel) and hasattr(tp, name):
                    tp = getattr(tp, name)
                return tp

            for k, v in fields.items():
                v.type_ = update_type(v.type_)
                v.prepare()

        cache = {}

        class ViewDesc:
            def __get__(self, obj, owner=None):
                nonlocal cache

                cache_key = f"{id(obj)}{type(obj)}{id(owner)}"
                if cache_key not in cache:

                    def __init__(self, **kwds):
                        if obj is not None:
                            if kwds:
                                raise TypeError()
                            kwds = {k: v for k, v in obj.dict().items() if k in include_ and k not in exclude_}

                        super(owner, self).__init__(**kwds)

                    cache[cache_key] = type(name, (cls,), {"__init__": __init__, "__fields__": fields})

                return cache[cache_key]

        setattr(cls, name, ViewDesc())

        return cls

    return wrapper
