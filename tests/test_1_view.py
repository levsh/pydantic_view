from typing import List, Optional, Tuple

import pytest
from pydantic import BaseModel, Field, ValidationError

from pydantic_view import view, view_validator


def test_model():
    @view("ViewA", exclude=["aa", "dd"])
    @view("ViewR", include=["cc"])
    class SubModel(BaseModel):
        aa: int
        bb: str
        cc: List[int]
        dd: int = None
        ee: Optional[str]

    @view("ViewA", exclude=["a", "d"])
    @view("ViewB", exclude=["c"], optional=["b"])
    @view("ViewC", include=["a"])
    @view("ViewR", include=["c"], recursive=True)
    @view("ViewO", include=["a", "b"], optional=["a"], optional_ex={"b": Field(default_factory=lambda: "B")})
    class Model(BaseModel):
        a: int
        b: str
        c: Tuple[SubModel, SubModel]
        d: int = None
        e: Optional[str]

    assert hasattr(Model, "ViewA")
    assert hasattr(Model, "ViewB")
    assert issubclass(Model.ViewA, Model)
    assert issubclass(Model.ViewA, BaseModel)
    assert issubclass(Model.ViewB, Model)
    assert issubclass(Model.ViewB, BaseModel)
    assert issubclass(Model.ViewC, Model)
    assert issubclass(Model.ViewC, BaseModel)
    assert Model.ViewA != Model.ViewB != Model.ViewC

    with pytest.raises(ValidationError):
        Model()

    model = Model(a=0, b="b", c=[SubModel(aa=1, bb="bb", cc=[1, 2]), {"aa": 2, "bb": "BB", "cc": [3, 4]}])

    assert issubclass(Model, BaseModel)
    assert isinstance(model, Model)
    assert isinstance(model, BaseModel)
    assert model.a == 0
    assert model.b == "b"
    assert model.c == (SubModel(aa=1, bb="bb", cc=[1, 2]), SubModel(aa=2, bb="BB", cc=[3, 4]))
    assert model.d is None
    assert model.e is None

    assert hasattr(model, "ViewA")
    assert hasattr(model, "ViewB")
    assert hasattr(model, "ViewC")
    assert issubclass(model.ViewA, Model)
    assert issubclass(model.ViewA, BaseModel)
    assert issubclass(model.ViewB, Model)
    assert issubclass(model.ViewB, BaseModel)
    assert issubclass(model.ViewC, Model)
    assert issubclass(model.ViewC, BaseModel)
    assert model.ViewA != model.ViewB != model.ViewC

    view_a = model.ViewA()
    assert isinstance(view_a, model.ViewA)
    assert isinstance(view_a, BaseModel)
    assert not hasattr(view_a, "a")
    assert not hasattr(view_a, "d")
    assert view_a.b == "b"
    assert view_a.c == (SubModel(aa=1, bb="bb", cc=[1, 2]), SubModel(aa=2, bb="BB", cc=[3, 4]))
    assert view_a.e is None
    assert view_a.dict() == {
        "b": "b",
        "c": (
            {"aa": 1, "bb": "bb", "cc": [1, 2], "dd": None, "ee": None},
            {"aa": 2, "bb": "BB", "cc": [3, 4], "dd": None, "ee": None},
        ),
        "e": None,
    }

    with pytest.raises(ValidationError):
        Model.ViewB()

    view_b = Model.ViewB(a=0, e="e")
    assert view_b.a == 0
    assert view_b.b is None
    assert not hasattr(view_b, "c")
    assert view_b.d is None
    assert view_b.e == "e"

    view_c = model.ViewC()
    assert view_c.a == 0
    assert not hasattr(view_c, "b")
    assert not hasattr(view_c, "c")
    assert not hasattr(view_c, "d")
    assert not hasattr(view_c, "e")

    view_r = model.ViewR()
    assert not hasattr(view_r, "a")
    assert not hasattr(view_r, "b")
    assert not hasattr(view_r, "d")
    assert not hasattr(view_r, "e")
    assert not hasattr(view_r.c[0], "aa")
    assert not hasattr(view_r.c[0], "bb")
    assert not hasattr(view_r.c[0], "dd")
    assert not hasattr(view_r.c[0], "ee")
    assert view_r.c[0].cc == [1, 2]
    assert not hasattr(view_r.c[1], "aa")
    assert not hasattr(view_r.c[1], "bb")
    assert not hasattr(view_r.c[1], "dd")
    assert not hasattr(view_r.c[1], "ee")
    assert view_r.c[1].cc == [3, 4]

    view_o = model.ViewO()
    assert view_o.a == 0
    assert view_o.b == "b"
    assert not hasattr(view_o, "c")
    assert not hasattr(view_o, "d")
    assert not hasattr(view_o, "e")

    view_o = Model.ViewO()
    assert view_o.a is None
    assert view_o.b == "B"
    assert not hasattr(view_o, "c")
    assert not hasattr(view_o, "d")
    assert not hasattr(view_o, "e")


def test__str():
    @view("View")
    class Model(BaseModel):
        i: int = None

    assert f"{Model.View}" == "<class 'tests.test_1_view.ModelView'>"
    model = Model()
    assert f"{model.View}" == "<class 'tests.test_1_view.ModelView'>"


def test_view_validator():
    @view("View")
    class Model(BaseModel):
        i: int = None
        s: str = None

        @view_validator(["View"], "s")
        def validate_s(cls, v, values):
            if v is not None and v != "ok":
                raise ValueError
            return v

    Model(a=1)
    Model(s="ok")
    Model(s="not ok")

    Model(a=1).View()
    Model(s="ok").View()
    with pytest.raises(ValidationError):
        Model(s="not ok").View()


def test_view_config():
    @view("View", config={"extra": "forbid"})
    class Model(BaseModel):
        i: int = None
        s: str = None

    Model(f=1.0)
    with pytest.raises(ValidationError):
        Model.View(f=1.0)
