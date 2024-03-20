from copy import copy
from types import UnionType
from typing import Union

from pydantic import BaseModel, create_model, field_validator, model_validator
from pydantic._internal._decorators import Decorator
from pydantic.errors import PydanticUndefinedAnnotation, PydanticUserError


def view(
    name: str,
    force: bool = False,
    attach: bool = True,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    recursive: bool = True,
):
    """
    Decorator to create a Pydantic model view.

    Args:
      name: view name.
      force: force recreate if view with same name already exists.
      attach: attach or not view to model as class attribute.
      include: set of field names to include from model.
      exclude: set of field names to exclude from model.
      recursive: ...
    """

    if name is not None and not isinstance(name, str):
        raise Exception("expect view name")

    if (include or set()) & (exclude or set()):
        raise ValueError("same fields in include and exclude are not allowed")

    def wrapper(
        view_cls,
        name=name,
        attach=attach,
        include=include,
        exclude=exclude,
        recursive=recursive,
    ):
        if hasattr(view_cls, "__pydantic_view_root_cls__"):
            root_cls = view_cls.__pydantic_view_root_cls__
        else:
            root_cls = view_cls.__base__

        if root_cls == BaseModel:
            raise Exception("invalid model for view")
        if not issubclass(view_cls, root_cls):
            raise Exception("view must inherit from the model")
        if not force and name in root_cls.__dict__:
            raise Exception("view with some name already exists")
        if set(view_cls.__dict__) & (exclude or set()):
            raise ValueError("view model fields conflict with exclude parameter")

        view_cls.__pydantic_view_params__ = {
            "name": name,
            "attach": attach,
            "include": include,
            "exclude": exclude,
            "recursive": recursive,
        }

        def build_view(root_cls, view_cls):
            base_view_params = getattr(view_cls.__mro__[1], "__pydantic_view_params__", {})
            view_params = view_cls.__pydantic_view_params__

            name = view_params["name"]

            include = view_params["include"]
            if include is None:
                include = set(view_cls.model_fields.keys())
            if base_view_params.get("include") is not None:
                include &= base_view_params["include"]

            exclude = view_params["exclude"]
            if exclude is None:
                exclude = set()
            if base_view_params.get("exclude") is not None:
                exclude |= base_view_params["exclude"]

            def update_type(tp):
                if hasattr(tp, "__origin__"):
                    return tp.__class__(
                        update_type(tp.__origin__),
                        tp.__metadata__
                        if hasattr(tp, "__metadata__")
                        else tuple(update_type(arg) for arg in tp.__args__),
                    )
                if type(tp) == UnionType:
                    return Union[tuple(update_type(arg) for arg in tp.__args__)]
                if isinstance(tp, type) and issubclass(tp, BaseModel):
                    if hasattr(tp, name):
                        return getattr(tp, name)
                return tp

            if recursive is True:
                fields = {k: copy(v) for k, v in view_cls.model_fields.items() if k in include and k not in exclude}
                for field_info in fields.values():
                    field_info.annotation = update_type(field_info.annotation)
                    if field_info.default_factory:
                        field_info.default_factory = update_type(field_info.default_factory)
            else:
                fields = {k: v for k, v in view_cls.model_fields.items() if k in include and k not in exclude}

            view_cls.model_fields = fields

            def find_fields_schema(schema):
                if schema["type"] != "model-fields":
                    return find_fields_schema(schema["schema"])
                return schema

            model_schema = view_cls.__pydantic_core_schema__["schema"]
            fields_schema = find_fields_schema(model_schema)

            fields_schema["fields"] = {k: v for k, v in fields_schema["fields"].items() if k in fields}

            def find_ref(schema):
                if schema["type"] != "model":
                    return find_fields_schema(schema["schema"])
                return schema["ref"]

            for k, v in root_cls.__dict__.items():
                if (info := getattr(v, "__pydantic_view_field_validator__", None)) is not None:
                    fn = getattr(root_cls, k)
                    if info["view_names"] is None or name in info["view_names"]:
                        view_cls.__pydantic_decorators__.field_validators[v.__name__] = Decorator(
                            cls_ref=find_ref(view_cls.__pydantic_core_schema__),
                            cls_var_name=v.__name__,
                            func=fn,
                            shim=None,
                            info=field_validator(*info["args"], **info["kwds"])(v).decorator_info,
                        )
                elif (info := getattr(v, "__pydantic_view_model_validator__", None)) is not None:
                    fn = getattr(root_cls, k)
                    if info["view_names"] is None or name in info["view_names"]:
                        view_cls.__pydantic_decorators__.model_validators[v.__name__] = Decorator(
                            cls_ref=find_ref(view_cls.__pydantic_core_schema__),
                            cls_var_name=v.__name__,
                            func=fn,
                            shim=None,
                            info=model_validator(**info["kwds"])(v).decorator_info,
                        )

            view_cls.model_rebuild(force=True)

            class ViewRootClsDesc:
                def __get__(self, obj, owner=None):
                    return root_cls

            class ViewNameClsDesc:
                def __get__(self, obj, owner=None):
                    return name

            setattr(view_cls, "__pydantic_view_name__", ViewNameClsDesc())
            setattr(view_cls, "__pydantic_view_root_cls__", ViewRootClsDesc())

            if attach:

                class ViewDesc:
                    def __get__(self, obj, owner=None):
                        if obj:

                            def view_factory():
                                return view_cls(
                                    **obj.model_dump(
                                        include=include or None,
                                        exclude=exclude or None,
                                        exclude_unset=True,
                                    )
                                )

                            view_factory.__pydantic_view_name__ = name
                            view_factory.__pydantic_view_root_cls__ = root_cls

                            return view_factory

                        return view_cls

                setattr(root_cls, name, ViewDesc())

            if not hasattr(root_cls, "__pydantic_view_views__"):
                setattr(root_cls, "__pydantic_view_views__", (view_cls,))
            else:
                setattr(
                    root_cls,
                    "__pydantic_view_views__",
                    tuple(
                        x
                        for x in root_cls.__pydantic_view_views__
                        if x.__pydantic_view_name__ != view_cls.__pydantic_view_name__
                    )
                    + (view_cls,),
                )

            return view_cls

        try:
            build_view(root_cls, view_cls)
        except PydanticUserError as e:
            if not "is not fully defined; you should define" in f"{e}":
                raise e
        except PydanticUndefinedAnnotation:
            pass

        original_views_rebuild = getattr(root_cls, "views_rebuild", None)
        if original_views_rebuild:

            def views_rebuild(cls):
                original_views_rebuild()
                build_view(root_cls, view_cls)

        else:

            def views_rebuild(cls):
                build_view(root_cls, view_cls)

        setattr(root_cls, "views_rebuild", classmethod(views_rebuild))

        return view_cls

    return wrapper


def reapply_base_views(cls):
    for view_cls in getattr(cls, "__pydantic_view_views__", ()):
        if cls.__base__.__pydantic_generic_metadata__["args"]:
            base = (view_cls[*cls.__base__.__pydantic_generic_metadata__["args"]], cls)
        else:
            base = (view_cls, cls)
        fields = {k: (v.annotation, v) for k, v in cls.model_fields.items() if k in cls.__annotations__}
        new_view_cls = create_model(
            f"_{cls.__name__}{view_cls.__pydantic_view_name__}",
            __base__=base,
            __module__=cls.__module__,
            **fields,
        )
        new_view_cls.model_config.update(view_cls.model_config)
        setattr(new_view_cls, "__pydantic_view_root_cls__", cls)
        view(force=True, **view_cls.__pydantic_view_params__)(new_view_cls)

    return cls


def view_field_validator(view_names: set[str], *args, **kwds):
    def wrapper(fn):
        fn.__pydantic_view_field_validator__ = {"view_names": view_names, "args": args, "kwds": kwds}
        return fn

    return wrapper


def view_model_validator(view_names: set[str] | None = None, **kwds):
    def wrapper(fn):
        fn.__pydantic_view_model_validator__ = {"view_names": view_names, "kwds": kwds}
        return fn

    return wrapper
