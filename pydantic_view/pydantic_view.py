from copy import deepcopy
from typing import Dict, List, Literal, Optional, Set, Tuple, Type, Union, _GenericAlias, get_origin

from pydantic import BaseModel, ConfigDict, Extra, create_model, field_validator, model_validator
from pydantic.errors import PydanticUserError
from pydantic.fields import FieldInfo


class SchemaNotFoundError(Exception):
    pass


def view(
    name: str,
    base: List[str] = None,
    include: Set[str] = None,
    exclude: Set[str] = None,
    optional: Set[str] = None,
    optional_not_none: Set[str] = None,
    fields: Dict[str, Union[Type, FieldInfo, Tuple[Type, FieldInfo]]] = None,
    recursive: bool = True,
    extra: Extra = None,
    config=None,
    postpone: bool = False,
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

            if config:
                __fields__["model_config"] = ConfigDict(**config)

            if (
                (optional & optional_not_none)
                | (optional & set(fields.keys()))
                | (optional_not_none & set(fields.keys()))
            ):
                raise Exception("Field should only present in the one of optional, optional_not_none or fields")

            if extra_fields := fields.keys() - __base__.model_fields.keys():
                raise Exception(f"Model has not fields '{list(extra_fields)}'")

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
                if field_name in fields:
                    value = fields[field_name]
                    if isinstance(value, FieldInfo):
                        if not value.annotation:
                            if recursive is True:
                                value.annotation = update_type(deepcopy(field_info.annotation))
                            else:
                                value.annotation = field_info.annotation
                        __fields__[field_name] = (value.annotation, value)
                    elif isinstance(value, (tuple, list)):
                        annotation = value[0]
                        if isinstance(value[1], FieldInfo):
                            value[1].annotation = annotation
                            __fields__[field_name] = (annotation, value[1])
                        else:
                            __fields__[field_name] = (annotation, FieldInfo(annotation=annotation, default=value[1]))
                    else:
                        __fields__[field_name] = (value, FieldInfo(annotation=value))
                else:
                    field_info = deepcopy(field_info)
                    if recursive is True:
                        field_info.annotation = update_type(field_info.annotation)
                    if field_name in optional:
                        field_info.annotation = Optional[field_info.annotation]
                        field_info.default = None
                    elif field_name in optional_not_none:
                        field_info.default = None
                        if get_origin(field_info.annotation) == Union:
                            params = tuple(x for x in field_info.annotation.__args__ if not issubclass(x, type(None)))
                            field_info.annotation = Union[params]  # noqa
                    __fields__[field_name] = (field_info.annotation, field_info)

            __validators__ = {}

            for attr_name, attr in cls.__dict__.items():
                # fmt: off
                if (
                    getattr(attr, "__pydantic_view_is_field_validator__", None)
                    and name in attr.__pydantic_view_validator_view_names__
                ):  # fmt: on
                    __validators__[attr_name] = field_validator(
                        *attr.__pydantic_view_validator_args__,
                        **attr.__pydantic_view_validator_kwds__,
                    )(attr)
                # fmt: off
                elif (
                    getattr(attr, "__pydantic_view_is_model_validator__", None)
                    and name in attr.__pydantic_view_model_validator_view_names__
                ):  # fmt: on
                    __validators__[attr_name] = model_validator(
                        *attr.__pydantic_view_model_validator_args__,
                        **attr.__pydantic_view_model_validator_kwds__,
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

            setattr(view_cls, "__pydantic_view_name__", ViewNameClsDesc())
            setattr(view_cls, "__pydantic_view_root_cls__", ViewRootClsDesc())

            view_cls.model_fields = {
                k: v for k, v in view_cls.model_fields.items() if k in include and k not in exclude
            }

            def find_model_schema(definitions):
                for definition in definitions:
                    if definition["type"] == "model" and definition["cls"] == view_cls:
                        return definition
                    schema = definition
                    while schema := schema.get("schema"):
                        if schema["type"] == "model" and schema["cls"] == view_cls:
                            return schema

            model_schema = find_model_schema(view_cls.__pydantic_core_schema__["definitions"])
            if model_schema is None:
                raise SchemaNotFoundError(name)

            def find_fields_schema(schema):
                if schema["type"] != "model-fields":
                    return find_fields_schema(schema["schema"])
                return schema

            fields_schema = find_fields_schema(model_schema["schema"])

            fields_schema["fields"] = {
                k: v for k, v in fields_schema["fields"].items() if k in include and k not in exclude
            }

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

                        view_factory.__pydantic_view_name__ = name
                        view_factory.__pydantic_view_root_cls__ = cls

                        return view_factory

                    return view_cls

            setattr(cls, name, ViewDesc())

            if "__pydantic_view_kwds__" not in cls.__dict__:
                setattr(cls, "__pydantic_view_kwds__", {})

            cls.__pydantic_view_kwds__[name] = view_kwds

            return cls

        error = False

        if not postpone:
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
            except (PydanticUserError, SchemaNotFoundError) as e:
                if isinstance(e, PydanticUserError) and "is not fully defined; you should define" not in f"{e}":
                    raise e
                error = True

        if error or postpone:
            if views_rebuild := getattr(cls, "views_rebuild", None):

                def rebuild():
                    views_rebuild()
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

                setattr(cls, "views_rebuild", rebuild)

            else:
                setattr(cls, "views_rebuild", build_view)

            return cls

    return wrapper


def view_field_validator(view_names: List[str], field_name: str, *validator_args, **validator_kwds):
    def wrapper(fn):
        fn.__pydantic_view_is_field_validator__ = True
        fn.__pydantic_view_validator_view_names__ = view_names
        fn.__pydantic_view_validator_args__ = (field_name,) + validator_args
        fn.__pydantic_view_validator_kwds__ = validator_kwds
        return fn

    return wrapper


def view_model_validator(view_names: List[str], *, mode: Literal["wrap", "before", "after"]):
    def wrapper(fn):
        fn.__pydantic_view_is_model_validator__ = True
        fn.__pydantic_view_model_validator_view_names__ = view_names
        fn.__pydantic_view_model_validator_args__ = ()
        fn.__pydantic_view_model_validator_kwds__ = {"mode": mode}
        return fn

    return wrapper


def reapply_base_views(cls):
    for view_kwds in getattr(cls, "__pydantic_view_kwds__", {}).values():
        view(**view_kwds)(cls)
    return cls
