from typing import Any, ForwardRef, List, Optional

import pytest
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from pydantic_view import reapply_base_views, view, view_field_validator, view_model_validator


def test_basic():
    class Model(BaseModel):
        x: int

    @view("View")
    class View(Model):
        pass

    assert Model.View
    assert Model.View.__module__ == Model.__module__
    assert set(Model.View.model_fields.keys()) == {"x"}
    assert issubclass(Model.View, Model)
    assert hasattr(Model.View, "__pydantic_view_name__")
    assert Model.View.__pydantic_view_name__ == "View"
    assert hasattr(Model.View, "__pydantic_view_root_cls__")
    assert Model.View.__pydantic_view_root_cls__ == Model
    assert Model.View(x=0)
    assert isinstance(Model.View(x=0), Model)
    assert hasattr(Model.View(x=0), "x")
    assert Model.View(x=0).x == 0
    assert Model.View(x=0).model_dump() == {"x": 0}

    with pytest.raises(TypeError):
        Model(x=1).View(x=0)
    assert Model(x=1).View
    assert Model(x=1).View()
    assert hasattr(Model(x=1).View, "__pydantic_view_name__")
    assert Model(x=1).View.__pydantic_view_name__ == "View"
    assert hasattr(Model(x=1).View, "__pydantic_view_root_cls__")
    assert Model(x=1).View.__pydantic_view_root_cls__ == Model
    assert isinstance(Model(x=1).View(), Model)
    assert hasattr(Model(x=1).View(), "x")
    assert Model(x=1).View().x == 1
    assert Model(x=1).View().model_dump() == {"x": 1}


def test_same_id():
    class Model(BaseModel):
        x: int

    @view("View")
    class View(Model):
        pass

    assert id(Model.View) == id(Model.View)


def test_include():
    class Model(BaseModel):
        x: int
        y: int

    @view("View", include={"x"})
    class View(Model):
        pass

    assert set(Model.model_fields.keys()) == {"x", "y"}
    assert Model.View
    assert set(Model.View.model_fields.keys()) == {"x"}
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
    assert set(Model(x=1, y=2).View().model_fields.keys()) == {"x"}
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().model_dump() == {"x": 1}


def test_exclude():
    class Model(BaseModel):
        x: int
        y: int

    @view("View", exclude={"y"})
    class View(Model):
        pass

    assert set(Model.model_fields.keys()) == {"x", "y"}
    assert Model.View
    assert set(Model.View.model_fields.keys()) == {"x"}
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
    assert set(Model(x=1, y=2).View().model_fields.keys()) == {"x"}
    assert hasattr(Model(x=1, y=2).View(), "x")
    assert not hasattr(Model(x=1, y=2).View(), "y")
    assert Model(x=1, y=2).View().x == 1
    assert Model(x=1, y=2).View().model_dump() == {"x": 1}


def test_redeclare():
    class Model(BaseModel):
        x: str
        y: int

    @view("View")
    class View(Model):
        x: int
        y: Optional[int] = None

    assert Model.model_fields["x"].annotation == str
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

    assert Model.View(x="0").x == 0
    assert Model.View(x="0").y is None
    assert Model.View(x="0").model_dump() == {"x": 0, "y": None}
    assert Model.View(x="0", y=1).x == 0
    assert Model.View(x="0", y=1).y == 1
    assert Model.View(x="0", y=1).model_dump() == {"x": 0, "y": 1}
    assert Model.View(x="0", y=None).x == 0
    assert Model.View(x="0", y=None).y is None
    assert Model.View(x="0", y=None).model_dump() == {"x": 0, "y": None}

    assert Model(x="0", y=1).View().x == 0
    assert Model(x="0", y=1).View().y == 1
    assert Model(x="0", y=1).View().model_dump() == {"x": 0, "y": 1}


def test_recursive():
    class SubModel(BaseModel):
        x: int
        y: int

    @view("View", include={"x"})
    class SubModelView(SubModel):
        pass

    class Model(BaseModel):
        x: int
        submodel: SubModel

    @view("View")
    class ModelView(Model):
        pass

    @view("ViewEx")
    class ModelViewEx(ModelView):
        pass

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
    class SubModel(BaseModel):
        x: int
        y: int

    @view("View", include={"x"})
    class SubModelView(SubModel):
        pass

    class Model(BaseModel):
        x: int
        submodels: List[SubModel]

    @view("View")
    class ModelView(Model):
        pass

    model = Model(x=0, submodels=[SubModel(x=0, y=1)])
    model_view = model.View()
    assert model_view.x == 0
    assert type(model_view.submodels[0]) == SubModel.View
    assert model_view.submodels[0].x == 0
    assert not hasattr(model_view.submodels[0], "y")


def test_str():
    class Model(BaseModel):
        x: int = None

    @view("View")
    class ModelView(Model):
        pass

    assert f"{Model.View}" == "<class 'tests.test_1_view.test_str.<locals>.ModelView'>"
    model = Model()
    assert f"{model}" == "x=None"


def test_validator():
    class Model(BaseModel):
        i: int = 1
        s: str = "a"

        @field_validator("i")
        @classmethod
        def validate_i_1(cls, v):
            return v * 2

        @field_validator("i")
        @classmethod
        def validate_i_2(cls, v):
            return v + v

        @field_validator("s")
        @classmethod
        def validate_s_1(cls, v):
            return v + v

        @field_validator("s")
        @classmethod
        def validate_s_2(cls, v):
            return f"{v}*{v}"

        @model_validator(mode="before")
        @classmethod
        def model_validate_i(cls, values):
            if values.get("i") == 100:
                raise ValueError
            return values

        @model_validator(mode="before")
        @classmethod
        def model_validate_s(cls, values):
            if values.get("s") == "100":
                raise ValueError
            return values

    @view("View")
    class ModelView(Model):
        @field_validator("i")
        @classmethod
        def validate_i(cls, v):
            return v * 3

        @field_validator("s")
        @classmethod
        def validate_s(cls, v):
            return v + v + v

        @model_validator(mode="before")
        @classmethod
        def model_validate_i(cls, values):
            if values.get("i") == 800:
                raise ValueError
            return values

        @model_validator(mode="before")
        @classmethod
        def model_validate_s(cls, values):
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
    class Model(BaseModel):
        a: Any

    @view("View")
    class View(Model):
        pass

    Model.View
    Model.View(a=1)
    Model(a=1).View()


def test_forward_refs_type():
    F = ForwardRef("F")

    class Model(BaseModel):
        f: "F"

    @view("View")
    class ModelView(Model):
        pass

    class F(BaseModel):
        f: float

    @view("View")
    class FView(F):
        pass

    Model.model_rebuild()
    ModelView.model_rebuild()
    ModelView.views_rebuild()

    assert Model.View
    assert Model.View(f={"f": 0.0}).f.f == 0.0
    assert Model(f={"f": 0.0}).View().f.f == 0.0


def test_recursive_list_with_base():
    class SubModel(BaseModel):
        x: int
        y: int

    @view("View", include={"x"})
    class SubModelView(SubModel):
        pass

    class Model(BaseModel):
        x: int
        submodels: list[SubModel]

    @view("View")
    class ModelView(Model):
        pass

    @view("ViewChild", include={"submodels"})
    class ModelViewChild(ModelView):
        pass

    model = Model(x=0, submodels=[SubModel(x=0, y=1)])
    model_view = model.ViewChild()
    assert not hasattr(model_view, "x")
    assert model_view.submodels
    assert type(model_view.submodels[0]) == SubModel.View
    assert model_view.submodels[0].x == 0
    assert not hasattr(model_view.submodels[0], "y")


def test_reapply_base_views():
    class Parent(BaseModel):
        x: int
        y: int

    @view("View", exclude={"y"})
    class ParentView(Parent):
        pass

    class ChildNotReapplied(Parent):
        z: int

    assert "z" not in ChildNotReapplied.View.model_fields

    @reapply_base_views
    class ChildReapplied(Parent):
        z: int

    assert "z" in ChildReapplied.View.model_fields


def test_view_validator():
    class Model(BaseModel):
        i: int

        @view_field_validator(["View"], "i")
        @classmethod
        def validate_i(cls, v):
            return v * 2

        @view_model_validator(["View"], mode="after")
        def validate_model(self):
            self.i *= 2
            return self

    @view("View")
    class ModelView(Model):
        pass

    assert Model(i=1).i == 1
    assert Model(i=1).View().i == 4
    assert Model.View(i=1).i == 4
