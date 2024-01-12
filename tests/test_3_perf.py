from time import monotonic

from pydantic import BaseModel

from pydantic_view import view


def test_perf():
    class SubModel(BaseModel):
        x: int = None

    @view("View")
    class SubModelView(SubModel):
        pass

    class Model(BaseModel):
        i: int
        f: float
        s: str
        sub: SubModel

    @view("View")
    class ModelView(Model):
        pass

    print()

    for _ in range(3):
        t0 = monotonic()
        [Model(i=1, f=1.1, s="a", sub=SubModel()) for _ in range(25**3)]
        t1 = monotonic() - t0
        print(t1)

        models = [Model(i=1, f=1.1, s="a", sub=SubModel()) for _ in range(25**3)]
        t0 = monotonic()
        [model.View() for model in models]
        t2 = monotonic() - t0
        print(t2)

        print(t2 / t1)

        assert t2 / t1 < 2

        print("-" * 50)
