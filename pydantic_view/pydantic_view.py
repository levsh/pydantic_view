from copy import deepcopy
from types import prepare_class, resolve_bases
from typing import Dict, List, Set, _GenericAlias

from pydantic import BaseConfig, BaseModel, validator
from pydantic.config import inherit_config
from pydantic.fields import FieldInfo


def view(
    name: str,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_ex: Dict[str, FieldInfo] = None,
    recursive: bool = None,
    config=None,
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
                elif isinstance(tp, type) and issubclass(tp, BaseModel) and hasattr(tp, name):
                    tp = getattr(tp, name)
                return tp

            for k, v in fields.items():
                if v.sub_fields:
                    for sub_field in v.sub_fields:
                        sub_field.type_ = update_type(sub_field.type_)
                v.type_ = update_type(v.type_)
                v.prepare()

        validators = {}

        for attr_name, attr in cls.__dict__.items():
            if getattr(attr, "_is_view_validator", None) and name in attr._view_validator_view_names:
                validators[attr_name] = validator(*attr._view_validator_args, **attr._view_validator_kwds)(attr)

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

                    view_cls_name = f"{cls.__name__}{name}"

                    bases = resolve_bases((cls,))
                    meta, ns, kwds = prepare_class(view_cls_name, bases)

                    namespace = {}

                    namespace.update(validators)
                    namespace.update(
                        {
                            "__module__": cls.__module__,
                            "__init__": __init__,
                            "__fields__": fields,
                        }
                    )

                    if config:
                        namespace["Config"] = inherit_config(type("Config", (), config), BaseConfig)

                    namespace.update(ns)

                    view_cls = meta(view_cls_name, bases, namespace, **kwds)

                    cache[cache_key] = view_cls

                    if validators:
                        for field_name, field in view_cls.__fields__.items():
                            for validator_ in view_cls.__validators__.get(field_name, []):
                                field.class_validators[validator_.func.__name__] = validator_
                            field.populate_validators()

                return cache[cache_key]

        setattr(cls, name, ViewDesc())

        return cls

    return wrapper


def view_validator(view_names: List[str], *validator_args, **validator_kwds):
    def wrapper(fn):
        fn._is_view_validator = True
        fn._view_validator_view_names = view_names
        fn._view_validator_args = validator_args
        fn._view_validator_kwds = validator_kwds
        return fn

    return wrapper
