from typing import Any, ForwardRef, List

import pytest
from pydantic import BaseModel, BaseSettings, SecretStr, ValidationError, root_validator, validator

from pydantic_view import reapply_base_views, view, view_root_validator, view_validator


def test_basic():
    @view("View")
    class Model(BaseModel):
        x: int

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).dict() == {"x": 0}
    assert hasattr(Model.View, "__view_name__")
    assert Model.View.__view_name__ == "View"
    assert hasattr(Model.View, "__view_root_cls__")
    assert Model.View.__view_root_cls__ == Model

    with pytest.raises(TypeError):
        Model(x=1).View(x=0)
    assert Model(x=1).View
    assert Model(x=1).View()
    assert hasattr(Model(x=1).View(), "x")
    assert not hasattr(Model(x=1).View(), "y")
    assert Model(x=1).View().x == 1
    assert Model(x=1).View().dict() == {"x": 1}
    assert hasattr(Model(x=1).View, "__view_name__")
    assert Model(x=1).View.__view_name__ == "View"
    assert hasattr(Model(x=1).View, "__view_root_cls__")
    assert Model(x=1).View.__view_root_cls__ == Model


def test_same_id():
    @view("View")
    class Model(BaseModel):
        x: int

    assert id(Model.View) == id(Model.View)
    assert id(Model(x=1).View) != id(Model(x=1).View)
    model = Model(x=1)
    assert id(model.View) == id(model.View)


def test_include():
    @view("View", include={"x"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).dict() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1, y=2).View(x=0)
    assert Model(x=1, y=2).View
    assert Model(x=1, y=2).View()
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().dict() == {"x": 1}


def test_exclude():
    @view("View", exclude={"y"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).dict() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1, y=2).View(x=0)
    assert Model(x=1, y=2).View
    assert Model(x=1, y=2).View()
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().dict() == {"x": 1}


def test_optional():
    @view("View", optional={"y"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).y is None
    assert Model.View(x=0).dict() == {"x": 0, "y": None}
    assert Model.View(x=0, y=1).x == 0
    assert Model.View(x=0, y=1).y == 1
    assert Model.View(x=0, y=1).dict() == {"x": 0, "y": 1}
    assert Model.View(x=0, y=None).x == 0
    assert Model.View(x=0, y=None).y is None
    assert Model.View(x=0, y=None).dict() == {"x": 0, "y": None}

    with pytest.raises(TypeError):
        Model(x=0, y=1).View(x=0)
    assert Model(x=0, y=1).View
    assert Model(x=0, y=1).View()
    assert hasattr(Model(x=0, y=1).View(), "x")
    assert hasattr(Model(x=0, y=1).View(), "y")
    assert Model(x=0, y=1).View().x == 0
    assert Model(x=0, y=1).View().y == 1
    assert Model(x=0, y=1).View().dict() == {"x": 0, "y": 1}


def test_optional_not_none():
    @view("View", optional_not_none={"y"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).y is None
    assert Model.View(x=0).dict() == {"x": 0, "y": None}
    assert Model.View(x=0, y=1).x == 0
    assert Model.View(x=0, y=1).y == 1
    assert Model.View(x=0, y=1).dict() == {"x": 0, "y": 1}
    with pytest.raises(ValidationError):
        assert Model.View(x=0, y=None)

    with pytest.raises(TypeError):
        Model(x=0, y=1).View(x=0)
    assert Model(x=0, y=1).View
    assert Model(x=0, y=1).View()
    assert hasattr(Model(x=0, y=1).View(), "x")
    assert hasattr(Model(x=0, y=1).View(), "y")
    assert Model(x=0, y=1).View().x == 0
    assert Model(x=0, y=1).View().y == 1
    assert Model(x=0, y=1).View().dict() == {"x": 0, "y": 1}


def test_recursive():
    @view("View", include={"x"})
    class SubModel(BaseModel):
        x: int
        y: int

    @view("ViewEx", base=["View"], recursive=True)
    @view("View", recursive=True)
    class Model(BaseModel):
        x: int
        submodel: SubModel

    model = Model(x=0, submodel=SubModel(x=0, y=1))

    model_view = model.View()
    assert model_view.x == 0
    assert model_view.submodel
    assert type(model_view.submodel) == SubModel.View
    assert model_view.submodel.x == 0
    assert not hasattr(model_view.submodel, "y")

    model_view = model.ViewEx()
    assert model_view.x == 0
    assert model_view.submodel
    assert type(model_view.submodel) == SubModel.View
    assert model_view.submodel.x == 0
    assert not hasattr(model_view.submodel, "y")


def test_recursive_list():
    @view("View", include={"x"})
    class SubModel(BaseModel):
        x: int
        y: int

    @view("View", recursive=True)
    class Model(BaseModel):
        x: int
        submodels: List[SubModel]

    model = Model(x=0, submodels=[SubModel(x=0, y=1)])
    model_view = model.View()
    assert model_view.x == 0
    assert model_view.submodels
    assert type(model_view.submodels[0]) == SubModel.View
    assert model_view.submodels[0].x == 0
    assert not hasattr(model_view.submodels[0], "y")


def test_str():
    @view("View")
    class Model(BaseModel):
        x: int = None

    assert f"{Model.View}" == "<class 'tests.test_1_view.ModelView'>"
    model = Model()
    assert f"{model.View}" == "<class 'tests.test_1_view.ModelView'>"
    assert f"{model}" == "x=None"


def test_validator():
    @view("View")
    class Model(BaseModel):
        i: int = None
        s: str = None

        @validator("i")
        def validate_i(cls, v):
            if v == 0:
                raise ValueError
            return v

        @root_validator
        def root_validate(cls, values):
            if values.get("i") == 1 and values.get("s") == "1":
                raise ValueError
            return values

        @view_validator(["View"], "i")
        def view_validate_i(cls, v):
            if v == 2:
                raise ValueError
            return v

        @view_root_validator(["View"])
        def view_root_validate(cls, values):
            if values.get("i") == 3 and values.get("s") == "3":
                raise ValueError
            return values

    with pytest.raises(ValidationError):
        Model(i=0)
    Model(i=1)
    with pytest.raises(ValidationError):
        Model(i=1, s="1")
    Model(i=1, s="2")

    with pytest.raises(ValidationError):
        Model(i=2).View()
    Model(i=1).View()
    with pytest.raises(ValidationError):
        Model(i=3, s="3").View()
    Model(i=3, s="4").View()


def test_config():
    @view("View", config={"extra": "forbid"})
    class Model(BaseModel):
        i: int = None

    Model(f=1.0)
    with pytest.raises(ValidationError):
        Model.View(f=1.0)


def test_any_type():
    @view("View")
    class Model(BaseModel):
        a: Any

    Model.View
    Model.View(a=1)
    Model(a=1).View()


F = ForwardRef("F")


@view("View")
class Model(BaseModel):
    f: "F"


@view("View")
class F(BaseModel):
    f: float


Model.update_forward_refs()
Model.View.update_forward_refs()


def test_forward_refs_type():
    assert Model.View
    assert Model.View(f={"f": 0.0}).f.f == 0.0
    assert Model(f={"f": 0.0}).View().f.f == 0.0


def test_extra():
    @view("ViewExtraForbid", extra="forbid")
    @view("ViewExtraIgnore", extra="ignore")
    class Model(BaseModel):
        x: int

    Model.ViewExtraIgnore(x=0)
    Model.ViewExtraForbid(x=0)

    Model.ViewExtraIgnore(x=0, y=1)
    with pytest.raises(ValidationError):
        Model.ViewExtraForbid(x=0, y=1)


def test_subviews():
    @view("ViewA")
    @view("ViewB", include={"x"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.ViewA
    assert Model.ViewA(x=0, y=1)
    model = Model(x=0, y=1)
    assert hasattr(model.ViewA(), "x")
    assert model.ViewA().x == 0
    assert model.ViewA().y == 1

    assert Model.ViewB
    assert Model.ViewB(x=0, y=1)
    model = Model(x=0, y=1)
    assert hasattr(model.ViewB(), "x")
    assert model.ViewB().x == 0
    assert not hasattr(model.ViewB(), "y")

    model = Model(x=0, y=1)
    assert hasattr(Model.ViewA, "ViewB")
    assert hasattr(model.ViewA, "ViewB")
    assert model.ViewA().ViewB()
    assert hasattr(model.ViewA().ViewB(), "x")
    assert model.ViewA().ViewB().x == 0
    assert not hasattr(model.ViewA().ViewB(), "y")
    assert hasattr(Model.ViewB, "ViewA")
    assert hasattr(model.ViewB, "ViewA")


def test_settings():
    @view("View")
    @view("ViewValidate")
    class Model(BaseSettings):
        x: int

        @view_validator(["ViewValidate"], "x")
        def validate_x(cls, v):
            if v == 0:
                raise ValueError
            return v

    assert Model.View
    assert Model.View(x=0)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).dict() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1).View(x=0)
    assert Model(x=1).View
    assert Model(x=1).View()
    assert hasattr(Model(x=1).View(), "x")
    assert not hasattr(Model(x=1).View(), "y")
    assert Model(x=1).View().x == 1
    assert Model(x=1).View().dict() == {"x": 1}

    assert Model.ViewValidate
    with pytest.raises(ValidationError):
        assert Model.ViewValidate(x=0)
    with pytest.raises(ValidationError):
        assert Model(x=0).ViewValidate()


def test_base():
    @view("OutShowSecrets", base=["Out"], include={"secret"}, fields={"secret": str})
    @view("Out")
    class Model(BaseModel):
        i: int
        secret: SecretStr

        @view_validator(["OutShowSecrets"], "secret", pre=True)
        def validate_secret(cls, v):
            if hasattr(v, "get_secret_value"):
                v = v.get_secret_value()
            return v

    assert Model.Out
    assert Model.OutShowSecrets
    assert issubclass(Model.OutShowSecrets, Model.Out)
    assert not hasattr(Model.OutShowSecrets(secret="secret"), "i")
    assert Model.OutShowSecrets(secret="abc").secret == "abc"
    assert Model(i=0, secret="abc").OutShowSecrets().secret == "abc"


def test_recursive_list_with_base():
    @view("View", include={"x"})
    class SubModel(BaseModel):
        x: int
        y: int

    @view("ViewChild", base=["View"], include={"submodels"})
    @view("View", recursive=True)
    class Model(BaseModel):
        x: int
        submodels: List[SubModel]

    model = Model(x=0, submodels=[SubModel(x=0, y=1)])
    model_view = model.ViewChild()
    assert not hasattr(model_view, "x")
    assert model_view.submodels
    assert type(model_view.submodels[0]) == SubModel.View
    assert model_view.submodels[0].x == 0
    assert not hasattr(model_view.submodels[0], "y")


def test_reapply_base_views():
    @view("View", exclude={"y"})
    class Parent(BaseModel):
        x: int
        y: int

    class ChildNotReapplied(Parent):
        z: int

    assert "z" not in ChildNotReapplied.View.__fields__

    @reapply_base_views
    class ChildReapplied(Parent):
        z: int

    assert "z" in ChildReapplied.View.__fields__
    assert issubclass(ChildReapplied.View, Parent)
    assert issubclass(ChildReapplied.View, Parent.View)
    assert not issubclass(Parent.View, ChildReapplied.View)


def test_root():
    @view("ViewC", root="ViewA.ViewB")
    @view("ViewB", root="ViewA")
    @view("ViewA", include={"i"})
    class Model(BaseModel):
        i: int
        j: int

    assert Model.ViewA
    assert not hasattr(Model, "ViewB")
    assert not hasattr(Model, "ViewC")
    assert Model.ViewA.ViewB
    assert not hasattr(Model.ViewA, "ViewC")
    assert Model.ViewA.ViewB.ViewC
