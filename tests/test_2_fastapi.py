from typing import List, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from pydantic_view import view, view_field_validator


@view("Out", exclude={"secret"})
@view("Create")
@view("Update")
@view("UpdateMany")
@view("Patch", optional_not_none={"public", "secret"})
@view("PatchMany", optional={"public", "secret"})
class UserSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public: Optional[str] = None
    secret: Optional[str] = None


@view("Out", exclude={"password"})
@view("Create", exclude=["id"], fields={"settings": Field(default_factory=UserSettings)})
@view("Update", exclude={"id"})
@view("UpdateMany")
@view("Patch", exclude={"id"}, optional_not_none={"username", "password", "settings"})
@view("PatchMany", optional_not_none={"username", "password", "settings"})
class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    username: str
    password: str = Field(default_factory=lambda: "password")
    settings: UserSettings

    @view_field_validator(["Create", "Update", "UpdateMany", "Patch", "PatchMany"], "username")
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError
        return v


app = FastAPI()

db = {}


@app.get("/users/{user_id}", response_model=User.Out)
async def get(user_id: int) -> User.Out:
    return db[user_id]


@app.post("/users", response_model=User.Out)
async def post(user: User.Create) -> User.Out:
    user_id = 0  # generate_user_id()
    db[0] = User(id=user_id, **user.model_dump())
    return db[0]


@app.put("/users/{user_id}", response_model=User.Out)
async def put(user_id: int, user: User.Update) -> User.Out:
    db[user_id] = User(id=user_id, **user.model_dump())
    return db[user_id]


@app.put("/users", response_model=List[User.Out])
async def put_many(users: List[User.UpdateMany]) -> List[User.Out]:
    for user in users:
        db[user.id] = user
    return users


@app.patch("/users/{user_id}", response_model=User.Out)
async def patch(user_id: int, user: User.Patch) -> User.Out:
    db[user_id] = User(**{**db[user_id].model_dump(), **user.model_dump(exclude_unset=True)})
    return db[user_id]


@app.patch("/users", response_model=List[User.Out])
async def patch_many(users: List[User.PatchMany]) -> List[User.Out]:
    for user in users:
        db[user.id] = User(**{**db[user.id].model_dump(), **user.model_dump(exclude_unset=True)})
    return [db[user.id] for user in users]


def test_fastapi():
    client = TestClient(app)

    # POST
    response = client.post(
        "/users",
        json={
            "username": "admin",
            "password": "admin",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": 0,
        "username": "admin",
        "settings": {"public": None},
    }

    # GET
    response = client.get("/users/0")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": 0,
        "username": "admin",
        "settings": {"public": None},
    }

    # PUT
    response = client.put(
        "/users/0",
        json={
            "username": "superadmin",
            "password": "superadmin",
            "settings": {"public": "foo", "secret": "secret"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": 0,
        "username": "superadmin",
        "settings": {"public": "foo"},
    }

    # PATCH
    response = client.patch(
        "/users/0",
        json={
            "username": "guest",
            "settings": {"public": "bar"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": 0,
        "username": "guest",
        "settings": {"public": "bar"},
    }
