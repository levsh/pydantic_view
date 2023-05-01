from typing import Dict, List, Optional, Set, Tuple, Type, Union, _GenericAlias

from pydantic import BaseModel, Extra, create_model, root_validator, validator
from pydantic.fields import FieldInfo


class CustomDict(dict):
    pass


def view(
    name: str,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_not_none: Set[str] = None,
    fields: Dict[str, Union[Type, FieldInfo, Tuple[Type, FieldInfo]]] = None,
    recursive: bool = None,
    extra: Extra = None,
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

        view_cls_name = f"{cls.__name__}{name}"

        __cls_kwargs__ = {}
        if extra:
            __cls_kwargs__["extra"] = extra

        view_cls = create_model(
            view_cls_name,
            __module__=cls.__module__,
            __base__=(cls,),
            __validators__=__validators__,
            __cls_kwargs__=__cls_kwargs__,
            **__fields__,
        )

        if config:
            config_cls = type("Config", (cls.Config,), config)
            view_cls = type(view_cls_name, (view_cls,), {"Config": config_cls})

        view_cls.__fields__ = {k: v for k, v in view_cls.__fields__.items() if k in include and k not in exclude}

        for field_name in optional_not_none:
            if field := view_cls.__fields__.get(field_name):
                field.allow_none = False

        if recursive is True:

            def update_type(tp):
                if isinstance(tp, _GenericAlias):
                    tp.__args__ = tuple(update_type(arg) for arg in tp.__args__)
                elif isinstance(tp, type) and issubclass(tp, BaseModel) and hasattr(tp, name):
                    tp = getattr(tp, name)
                return tp

            for k, v in view_cls.__fields__.items():
                if v.sub_fields:
                    for sub_field in v.sub_fields:
                        sub_field.type_ = update_type(sub_field.type_)
                        # sub_field.outer_type_ = update_type(sub_field.outer_type_)
                        sub_field.prepare()
                v.type_ = update_type(v.type_)
                # v.outer_type_ = update_type(v.outer_type_)
                v.prepare()

        class ViewDesc:
            def __get__(self, obj, owner=None):
                if obj:
                    if not hasattr(obj.__dict__, f"_{view_cls_name}"):

                        def __init__(self):
                            kwds = {k: v for k, v in obj.dict().items() if k in include and k not in exclude}
                            super(cls, self).__init__(**kwds)

                        object.__setattr__(obj, "__dict__", CustomDict(**obj.__dict__))
                        setattr(
                            obj.__dict__,
                            f"_{view_cls_name}",
                            type(
                                view_cls_name,
                                (view_cls,),
                                {
                                    "__module__": cls.__module__,
                                    "__init__": __init__,
                                },
                            ),
                        )

                    return getattr(obj.__dict__, f"_{view_cls_name}")

                return view_cls

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
