from types import prepare_class, resolve_bases
from typing import Dict, List, Optional, Set, Tuple, Type, Union, _GenericAlias

from pydantic import BaseConfig, BaseModel, create_model, root_validator, validator
from pydantic.config import inherit_config
from pydantic.fields import FieldInfo


def view(
    name: str,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_not_none: Set[str] = None,
    fields: Dict[str, Union[Type, FieldInfo, Tuple[Type, FieldInfo]]] = None,
    recursive: bool = None,
    config=None,
):
    if not include:
        include = set()
    if not exclude:
        exclude = set()
    if not optional:
        optional = set()
    if not optional_not_none:
        optional_not_none = set()
    if not fields:
        fields = {}
    if recursive is None:
        recursive = None
    if config is None:
        config = {}

    def wrapper(
        cls,
        name=name,
        include=set(include),
        exclude=set(exclude),
        optional=set(optional),
        optional_not_none=set(optional_not_none),
        fields=fields,
        recursive=recursive,
        config=config,
    ):
        if include and exclude:
            raise ValueError("include and exclude cannot be used together")

        include = include or set(cls.__fields__.keys())

        __fields__ = {}

        if (optional & optional_not_none) | (optional & set(fields.keys())) | (optional_not_none & set(fields.keys())):
            raise Exception("Field should only present in the one of optional, optional_not_none or fields")

        for field_name in optional | optional_not_none:
            if (field := cls.__fields__.get(field_name)) is None:
                raise Exception(f"Model has not field '{field_name}'")
            __fields__[field_name] = (Optional[field.outer_type_], field.field_info)

        for field_name, value in fields.items():
            if (field := cls.__fields__.get(field_name)) is None:
                raise Exception(f"Model has not field '{field_name}'")
            if isinstance(value, (tuple, list)):
                __fields__[field_name] = value
            elif isinstance(value, FieldInfo):
                __fields__[field_name] = (field.type_, value)
            else:
                __fields__[field_name] = (value, field.field_info)

        __validators__ = {}

        for attr_name, attr in cls.__dict__.items():
            if getattr(attr, "_is_view_validator", None) and name in attr._view_validator_view_names:
                __validators__[attr_name] = validator(
                    *attr._view_validator_args,
                    **attr._view_validator_kwds,
                )(attr)
            elif getattr(attr, "_is_view_root_validator", None) and name in attr._view_root_validator_view_names:
                __validators__[attr_name] = root_validator(
                    *attr._view_root_validator_args,
                    **attr._view_root_validator_kwds,
                )(attr)

        Base = create_model(
            f"{cls.__name__}{name}Base",
            __base__=(cls,),
            __validators__=__validators__,
            **__fields__,
        )

        Base.__fields__ = {k: v for k, v in Base.__fields__.items() if k in include and k not in exclude}

        for field_name in optional_not_none:
            if field := Base.__fields__.get(field_name):
                field.allow_none = False

        if recursive is True:

            def update_type(tp):
                if isinstance(tp, _GenericAlias):
                    tp.__args__ = tuple(update_type(arg) for arg in tp.__args__)
                elif isinstance(tp, type) and issubclass(tp, BaseModel) and hasattr(tp, name):
                    tp = getattr(tp, name)
                return tp

            for k, v in Base.__fields__.items():
                if v.sub_fields:
                    for sub_field in v.sub_fields:
                        sub_field.type_ = update_type(sub_field.type_)
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
                            kwds = {k: v for k, v in obj.dict().items() if k in include and k not in exclude}

                        super(cls, self).__init__(**kwds)

                    view_cls_name = f"{cls.__name__}{name}"

                    bases = resolve_bases((Base,))
                    meta, ns, kwds = prepare_class(view_cls_name, bases)

                    namespace = {}
                    namespace.update(
                        {
                            "__module__": cls.__module__,
                            "__init__": __init__,
                            "Config": inherit_config(type("Config", (), config), BaseConfig),
                        }
                    )

                    namespace.update(ns)

                    view_cls = meta(view_cls_name, bases, namespace, **kwds)

                    cache[cache_key] = view_cls

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


def view_root_validator(view_names: List[str], *validator_args, **validator_kwds):
    def wrapper(fn):
        fn._is_view_root_validator = True
        fn._view_root_validator_view_names = view_names
        fn._view_root_validator_args = validator_args
        fn._view_root_validator_kwds = validator_kwds
        return fn

    return wrapper
