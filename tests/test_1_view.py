from typing import Any, ForwardRef, List, Optional

import pytest
from pydantic import BaseModel, SecretStr, ValidationError, field_validator, model_validator

from pydantic_view import reapply_base_views, view, view_field_validator, view_model_validator

# from pydantic_settings import BaseSettings


def test_basic():
    @view("View")
    class Model(BaseModel):
        x: int

    assert Model.View
    assert issubclass(Model.View, Model)
    assert Model.View(x=0)
    assert isinstance(Model.View(x=0), Model)
    assert hasattr(Model.View(x=0), "x")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).model_dump() == {"x": 0}
    assert hasattr(Model.View, "__pydantic_view_name__")
    assert Model.View.__pydantic_view_name__ == "View"
    assert hasattr(Model.View, "__pydantic_view_root_cls__")
    assert Model.View.__pydantic_view_root_cls__ == Model

    with pytest.raises(TypeError):
        Model(x=1).View(x=0)
    assert Model(x=1).View
    assert Model(x=1).View()
    assert isinstance(Model(x=1).View(), Model)
    assert hasattr(Model(x=1).View(), "x")
    assert Model(x=1).View().x == 1
    assert Model(x=1).View().model_dump() == {"x": 1}
    assert hasattr(Model(x=1).View, "__pydantic_view_name__")
    assert Model(x=1).View.__pydantic_view_name__ == "View"
    assert hasattr(Model(x=1).View, "__pydantic_view_root_cls__")
    assert Model(x=1).View.__pydantic_view_root_cls__ == Model


def test_same_id():
    @view("View")
    class Model(BaseModel):
        x: int

    assert id(Model.View) == id(Model.View)
    assert id(Model(x=1).View) != id(Model(x=1).View)


def test_include():
    @view("View", include={"x"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert issubclass(Model.View, Model)
    assert Model.View(x=0)
    assert isinstance(Model.View(x=0), Model)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).model_dump() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1, y=2).View(x=0)
    assert Model(x=1, y=2).View
    assert Model(x=1, y=2).View()
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().model_dump() == {"x": 1}


def test_exclude():
    @view("View", exclude={"y"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View
    assert issubclass(Model.View, Model)
    assert Model.View(x=0)
    assert isinstance(Model.View(x=0), Model)
    assert hasattr(Model.View(x=0), "x")
    assert not hasattr(Model.View(x=0), "y")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).model_dump() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1, y=2).View(x=0)
    assert Model(x=1, y=2).View
    assert Model(x=1, y=2).View()
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().model_dump() == {"x": 1}


def test_optional():
    @view("View", optional={"y"})
    class Model(BaseModel):
        x: int
        y: int

    assert Model.View(x=0).x == 0
    assert Model.View(x=0).y is None
    assert Model.View(x=0).model_dump() == {"x": 0, "y": None}
    assert Model.View(x=0, y=1).x == 0
    assert Model.View(x=0, y=1).y == 1
    assert Model.View(x=0, y=1).model_dump() == {"x": 0, "y": 1}
    assert Model.View(x=0, y=None).x == 0
    assert Model.View(x=0, y=None).y is None
    assert Model.View(x=0, y=None).model_dump() == {"x": 0, "y": None}

    assert Model(x=0, y=1).View().x == 0
    assert Model(x=0, y=1).View().y == 1
    assert Model(x=0, y=1).View().model_dump() == {"x": 0, "y": 1}

    assert Model.model_fields["x"].annotation == int
    assert Model.model_fields["x"].is_required() is True
    assert Model.model_fields["x"].default is not None
    assert Model.model_fields["y"].annotation == int
    assert Model.model_fields["y"].is_required() is True
    assert Model.model_fields["y"].default is not None
    assert Model.View.model_fields["x"].annotation == int
    assert Model.View.model_fields["x"].is_required() is True
    assert Model.View.model_fields["x"].default is not None
    assert Model.View.model_fields["y"].annotation == Optional[int]
    assert Model.View.model_fields["y"].is_required() is False
    assert Model.View.model_fields["y"].default is None


def test_optional_not_none():
    @view("View", optional_not_none={"y", "z", "w"})
    class Model(BaseModel):
        x: int
        y: int
        z: int = None
        w: Optional[int] = None

    assert Model.View(x=0).x == 0
    assert Model.View(x=0).y is None
    assert Model.View(x=0).z is None
    assert Model.View(x=0).w is None
    assert Model.View(x=0).model_dump() == {"x": 0, "y": None, "z": None, "w": None}
    assert Model.View(x=0, y=1, z=2, w=3).model_dump() == {"x": 0, "y": 1, "z": 2, "w": 3}
    with pytest.raises(ValidationError):
        assert Model.View(x=0, y=None)
    with pytest.raises(ValidationError):
        assert Model.View(x=0, z=None)
    with pytest.raises(ValidationError):
        assert Model.View(x=0, w=None)

    assert Model(x=0, y=1).View().x == 0
    assert Model(x=0, y=1).View().y == 1
    assert Model(x=0, y=1).View().z is None
    assert Model(x=0, y=1).View().w is None
    assert Model(x=0, y=1).View().model_dump() == {"x": 0, "y": 1, "z": None, "w": None}
    assert Model(x=0, y=1, z=2, w=3).View().model_dump() == {"x": 0, "y": 1, "z": 2, "w": 3}
    with pytest.raises(ValidationError):
        assert Model.View(x=0, y=None)
    with pytest.raises(ValidationError):
        assert Model.View(x=0, z=None)
    with pytest.raises(ValidationError):
        assert Model.View(x=0, w=None)


def test_recursive():
    @view("View", include={"x"})
    class SubModel(BaseModel):
        x: int
        y: int

    @view("ViewEx", base=["View"])
    @view("View")
    class Model(BaseModel):
        x: int
        submodel: SubModel

    model = Model(x=0, submodel=SubModel(x=0, y=1))
    assert isinstance(model.submodel, SubModel)
    assert model.submodel.__class__ == SubModel
    model_view = model.View()
    assert model_view.x == 0
    assert type(model_view.submodel) == SubModel.View
    assert model_view.submodel.x == 0
    assert not hasattr(model_view.submodel, "y")

    model_view = model.ViewEx()
    assert model_view.x == 0
    assert type(model_view.submodel) == SubModel.View
    assert model_view.submodel.x == 0
    assert not hasattr(model_view.submodel, "y")


def test_recursive_list():
    @view("View", include={"x"})
    class SubModel(BaseModel):
        x: int
        y: int

    @view("View")
    class Model(BaseModel):
        x: int
        submodels: List[SubModel]

    model = Model(x=0, submodels=[SubModel(x=0, y=1)])
    model_view = model.View()
    assert model_view.x == 0
    assert type(model_view.submodels[0]) == SubModel.View
    assert model_view.submodels[0].x == 0
    assert not hasattr(model_view.submodels[0], "y")


def test_str():
    @view("View")
    class Model(BaseModel):
        x: int = None

    assert f"{Model.View}" == "<class 'tests.test_1_view.ModelView'>"
    model = Model()
    assert f"{model}" == "x=None"


def test_validator():
    @view("View")
    class Model(BaseModel):
        i: int = 1
        s: str = "a"

        @field_validator("i")
        def validate_i_1(cls, v):
            return v * 2

        @field_validator("i")
        def validate_i_2(cls, v):
            return v + v

        @field_validator("s")
        def validate_s_1(cls, v):
            return v + v

        @field_validator("s")
        def validate_s_2(cls, v):
            return f"{v}*{v}"

        @model_validator(mode="before")
        def model_validate_i(cls, values):
            if values.get("i") == 100:
                raise ValueError
            return values

        @model_validator(mode="before")
        def model_validate_s(cls, values):
            if values.get("s") == "100":
                raise ValueError
            return values

        @view_field_validator(["View"], "i")
        def view_field_validate_i(cls, v):
            return v * 3

        @view_field_validator(["View"], "s")
        def view_field_validate_s(cls, v):
            return v + v + v

        @view_model_validator(["View"], mode="before")
        def view_model_validate_i(cls, values):
            if values.get("i") == 800:
                raise ValueError
            return values

        @view_model_validator(["View"], mode="before")
        def view_model_validate_s(cls, values):
            if values.get("s") == "200200*200200":
                raise ValueError
            return values

    assert Model().i == 1
    assert Model().s == "a"
    assert Model(i=2).i == 8
    assert Model(i=2).s == "a"
    assert Model(s="a").i == 1
    assert Model(s="a").s == "aa*aa"
    with pytest.raises(ValidationError):
        Model(i=100)
    with pytest.raises(ValidationError):
        Model(s="100")

    assert Model().View().i == 1
    assert Model().View().s == "a"
    assert Model(i=2).View().i == 96
    assert Model(i=2).View().s == "a"
    assert Model(s="a").View().i == 1
    assert Model(s="a").View().s == "aa*aaaa*aa*aa*aaaa*aaaa*aaaa*aa*aa*aaaa*aaaa*aaaa*aa*aa*aaaa*aa"
    with pytest.raises(ValidationError):
        Model(i=200).View()
    with pytest.raises(ValidationError):
        Model(s="200").View()


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


Model.model_rebuild()
Model.views_rebuild()


def test_forward_refs_type():
    assert Model.View
    assert Model.View(f={"f": 0.0}).f.f == 0.0
    assert Model(f={"f": 0.0}).View().f.f == 0.0


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
    # assert hasattr(model.ViewA, "ViewB")
    assert model.ViewA().ViewB()
    assert hasattr(model.ViewA().ViewB(), "x")
    assert model.ViewA().ViewB().x == 0
    assert not hasattr(model.ViewA().ViewB(), "y")
    assert hasattr(Model.ViewB, "ViewA")
    # assert hasattr(model.ViewB, "ViewA")


def test_fields():
    @view("View", fields={"i": float})
    class Model(BaseModel):
        i: int

    assert Model.model_fields["i"].annotation == int
    assert Model.View.model_fields["i"].annotation == float


def test_base():
    @view("OutShowSecrets", base=["Out"], include={"secret"}, fields={"secret": str})
    @view("Out")
    class Model(BaseModel):
        i: int
        secret: SecretStr

        @view_field_validator(["OutShowSecrets"], "secret", mode="before")
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

    assert "z" not in ChildNotReapplied.View.model_fields

    @reapply_base_views
    class ChildReapplied(Parent):
        z: int

    assert "z" in ChildReapplied.View.model_fields
