from typing import Dict, List, Literal, Optional, Set, Tuple, Type, Union, _GenericAlias

from pydantic import BaseModel, Extra, create_model, field_validator, model_validator
from pydantic.errors import PydanticUserError
from pydantic.fields import FieldInfo


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
        def build_view(
            cls=cls,
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

            include = include or set(__base__.model_fields.keys())

            __fields__ = {}

            if (
                (optional & optional_not_none)
                | (optional & set(fields.keys()))
                | (optional_not_none & set(fields.keys()))
            ):
                raise Exception("Field should only present in the one of optional, optional_not_none or fields")

            for field_name, value in fields.items():
                if (field_info := __base__.model_fields.get(field_name)) is None:
                    raise Exception(f"Model has not field '{field_name}'")
                if isinstance(value, (tuple, list)):  # (type, value|FieldInfo)
                    __fields__[field_name] = value
                elif isinstance(value, FieldInfo):
                    __fields__[field_name] = (field_info.annotation, value)
                else:
                    __fields__[field_name] = (value, field_info)

            def update_type(tp):
                if isinstance(tp, _GenericAlias):
                    tp.__args__ = tuple(update_type(arg) for arg in tp.__args__)
                elif isinstance(tp, type) and issubclass(tp, BaseModel):
                    for _name in (name, *(base or [])):
                        if hasattr(tp, _name):
                            tp = getattr(tp, _name)
                            break
                return tp

            for field_name, field_info in __base__.model_fields.items():
                if field_name in __fields__:
                    annotation, field_info = __fields__[field_name]
                else:
                    annotation = field_info.annotation
                if recursive is True:
                    annotation = update_type(annotation)
                if field_name in optional:
                    __fields__[field_name] = (Optional[annotation], field_info)
                    __fields__[field_name][1].default = None
                elif field_name in optional_not_none:
                    __fields__[field_name] = (annotation, field_info)
                    __fields__[field_name][1].default = None
                else:
                    __fields__[field_name] = (annotation, field_info)

            __validators__ = {}

            for attr_name in dir(cls):
                if attr_name.startswith("__"):
                    continue
                attr = getattr(cls, attr_name)
                if getattr(attr, "_is_view_validator", None) and name in attr._view_validator_view_names:
                    __validators__[attr_name] = field_validator(
                        *attr._view_validator_args,
                        **attr._view_validator_kwds,
                    )(attr)
                elif getattr(attr, "_is_view_model_validator", None) and name in attr._view_model_validator_view_names:
                    __validators__[attr_name] = model_validator(
                        *attr._view_model_validator_args,
                        **attr._view_model_validator_kwds,
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
                view_cls = type(view_cls_name, (view_cls,), {"__module__": cls.__module__, "Config": config_cls})

            view_cls.model_fields = {
                k: v for k, v in view_cls.model_fields.items() if k in include and k not in exclude
            }

            definition = next(
                filter(
                    lambda d: d["type"] == "model" and d["cls"] == view_cls,
                    view_cls.__pydantic_core_schema__["definitions"],
                )
            )

            def find_schema(schema):
                if schema["type"] != "model-fields":
                    return find_schema(schema["schema"])
                return schema

            schema = find_schema(definition["schema"])

            schema["fields"] = {k: v for k, v in schema["fields"].items() if k in include and k not in exclude}

            view_cls.model_rebuild(force=True)

            class ViewDesc:
                def __get__(self, obj, owner=None):
                    if obj:

                        def view_factory():
                            return view_cls(
                                **{
                                    k: v
                                    for k, v in obj.model_dump(exclude_unset=True).items()
                                    if k in include and k not in exclude
                                }
                            )

                        view_factory.__view_name__ = name
                        view_factory.__view_root_cls__ = cls

                        return view_factory

                    return view_cls

            setattr(cls, name, ViewDesc())

            if "__pydantic_view_kwds__" not in cls.__dict__:
                setattr(cls, "__pydantic_view_kwds__", {})

            cls.__pydantic_view_kwds__[name] = view_kwds

            return cls

        try:
            cls.__pydantic_core_schema__
            return build_view(
                cls=cls,
                name=name,
                include=include,
                exclude=exclude,
                optional=optional,
                optional_not_none=optional_not_none,
                fields=fields,
                recursive=recursive,
                config=config,
            )
        except PydanticUserError as e:
            if "is not fully defined; you should define" not in f"{e}":
                raise e

            if rebuild_views := getattr(cls, "views_rebild", None):

                def rebuild_views():
                    rebuild_views()
                    build_view(
                        cls=cls,
                        name=name,
                        include=include,
                        exclude=exclude,
                        optional=optional,
                        optional_not_none=optional_not_none,
                        fields=fields,
                        recursive=recursive,
                        config=config,
                    )

            else:
                setattr(cls, "views_rebuild", build_view)

            return cls

    return wrapper


def view_field_validator(view_names: List[str], field_name: str, *validator_args, **validator_kwds):
    def wrapper(fn):
        fn._is_view_validator = True
        fn._view_validator_view_names = view_names
        fn._view_validator_args = (field_name,) + validator_args
        fn._view_validator_kwds = validator_kwds
        return fn

    return wrapper


def view_model_validator(view_names: List[str], *, mode: Literal["wrap", "before", "after"]):
    def wrapper(fn):
        fn._is_view_model_validator = True
        fn._view_model_validator_view_names = view_names
        fn._view_model_validator_args = ()
        fn._view_model_validator_kwds = {"mode": mode}
        return fn

    return wrapper


def reapply_base_views(cls):
    for view_kwds in getattr(cls, "__pydantic_view_kwds__", {}).values():
        view(**view_kwds)(cls)
    return cls
