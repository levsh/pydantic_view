from typing import Dict, List, Optional, Set, Tuple, Type, Union, _GenericAlias

from pydantic import BaseModel, Extra, create_model, root_validator, validator
from pydantic.fields import FieldInfo


class CustomDict(dict):
    pass


def view(
    name: str,
    base: List[str] = None,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_not_none: Set[str] = None,
    fields: Dict[str, Union[Type, FieldInfo, Tuple[Type, FieldInfo]]] = None,
    recursive: bool = None,
    extra: Extra = None,
    config=None,
):
    if include is None:
        include = set()
    if exclude is None:
        exclude = set()
    if optional is None:
        optional = set()
    if optional_not_none is None:
        optional_not_none = set()
    if fields is None:
        fields = {}
    if recursive is None:
        recursive = True
    if config is None:
        config = {}

    view_kwds = dict(
        name=name,
        base=base,
        include=include,
        exclude=exclude,
        optional=optional,
        optional_not_none=optional_not_none,
        fields=fields,
        recursive=recursive,
        extra=extra,
        config=config,
    )

    def wrapper(
        cls,
        name=name,
        include=include,
        exclude=exclude,
        optional=optional,
        optional_not_none=optional_not_none,
        fields=fields,
        recursive=recursive,
        config=config,
    ):
        __base__ = cls
        for view in base or []:
            if hasattr(cls, view):
                __base__ = getattr(cls, view)
                break

        if include and exclude:
            raise ValueError("include and exclude cannot be used together")

        include = include or set(__base__.__fields__.keys())

        __fields__ = {}

        if (optional & optional_not_none) | (optional & set(fields.keys())) | (optional_not_none & set(fields.keys())):
            raise Exception("Field should only present in the one of optional, optional_not_none or fields")

        for field_name in optional | optional_not_none:
            if (field := __base__.__fields__.get(field_name)) is None:
                raise Exception(f"Model has not field '{field_name}'")
            __fields__[field_name] = (Optional[field.outer_type_], field.field_info)

        for field_name, value in fields.items():
            if (field := __base__.__fields__.get(field_name)) is None:
                raise Exception(f"Model has not field '{field_name}'")
            if isinstance(value, (tuple, list)):
                __fields__[field_name] = value
            elif isinstance(value, FieldInfo):
                __fields__[field_name] = (field.type_, value)
            else:
                __fields__[field_name] = (value, field.field_info)

        __validators__ = {}

        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
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
            __base__=(__base__,),
            __validators__=__validators__,
            __cls_kwargs__=__cls_kwargs__,
            **__fields__,
        )

        class ViewRootClsDesc:
            def __get__(self, obj, owner=None):
                return cls

        class ViewNameClsDesc:
            def __get__(self, obj, owner=None):
                return name

        setattr(view_cls, "__view_name__", ViewNameClsDesc())
        setattr(view_cls, "__view_root_cls__", ViewRootClsDesc())

        if config:
            config_cls = type("Config", (__base__.Config,), config)
            view_cls = type(view_cls_name, (view_cls,), {"Config": config_cls})

        view_cls.__fields__ = {k: v for k, v in view_cls.__fields__.items() if k in include and k not in exclude}

        for field_name in optional | optional_not_none:
            if field := view_cls.__fields__.get(field_name):
                field.required = False

        for field_name in optional_not_none:
            if field := view_cls.__fields__.get(field_name):
                field.allow_none = False

        if recursive is True:

            def update_type(tp):
                if isinstance(tp, _GenericAlias):
                    tp.__args__ = tuple(update_type(arg) for arg in tp.__args__)
                elif isinstance(tp, type) and issubclass(tp, BaseModel):
                    for _name in (name, *tp.__bases__):
                        if hasattr(tp, name):
                            tp = getattr(tp, name)
                            break
                return tp

            def update_field_type(field):
                if field.sub_fields:
                    for sub_field in field.sub_fields:
                        update_field_type(sub_field)
                else:
                    field.type_ = update_type(field.type_)
                    field.prepare()
                if (
                    isinstance(field.default_factory, type)
                    and issubclass(field.default_factory, BaseModel)
                    and hasattr(field.default_factory, name)
                ):
                    field.default_factory = getattr(field.default_factory, name)

            for field in view_cls.__fields__.values():
                update_field_type(field)

        for field_name in optional_not_none:
            if field := view_cls.__fields__.get(field_name):
                field.allow_none = False

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

        if "__pydantic_view_kwds__" not in cls.__dict__:
            setattr(cls, "__pydantic_view_kwds__", {})

        cls.__pydantic_view_kwds__[name] = view_kwds

        return cls

    return wrapper


def view_validator(view_names: List[str], field_name: str, *validator_args, **validator_kwds):
    def wrapper(fn):
        fn._is_view_validator = True
        fn._view_validator_view_names = view_names
        fn._view_validator_args = (field_name,) + validator_args
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


def reapply_base_views(cls):
    for view_kwds in getattr(cls, "__pydantic_view_kwds__", {}).values():
        view(**view_kwds)(cls)
    return cls
