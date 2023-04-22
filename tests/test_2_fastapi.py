from typing import List

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from pydantic_view import view


@view("Out", exclude=["secret"])
@view("Create", exclude=["id"])
@view("Update", exclude=["id"])
@view("UpdateMany")
@view("Patch", exclude=["id"], optional=["name", "secret"])
@view("PatchMany", optional=["name", "secret"])
class Group(BaseModel):
    id: int
    name: str
    secret: str = None


@view("Out", exclude=["password"], recursive=True)
@view("Create", exclude=["id"], optional_ex={"groups": Field(default_factory=lambda: [Group(id=0, name="default")])})
@view("Update", exclude=["id"])
@view("UpdateMany")
@view("Patch", exclude=["id"], optional=["username", "password", "groups"])
@view("PatchMany", optional=["username", "password", "groups"])
class User(BaseModel):
    id: int
    username: str
    password: str
    groups: List[Group]


app = FastAPI()

db = {}


@app.get("/users/{user_id}", response_model=User.Out)
async def get(user_id: int) -> User.Out:
    return db[user_id]


@app.post("/users", response_model=User.Out)
async def post(user: User.Create) -> User.Out:
    user_id = 0  # generate_user_id()
    db[0] = User(id=user_id, **user.dict())
    return db[0]


@app.put("/users/{user_id}", response_model=User.Out)
async def put(user_id: int, user: User.Update) -> User.Out:
    db[user_id] = User(id=user_id, **user.dict())
    return db[user_id]


@app.put("/users", response_model=List[User.Out])
async def put_many(users: List[User.UpdateMany]) -> List[User.Out]:
    for user in users:
        db[user.id] = user
    return users


@app.patch("/users/{user_id}", response_model=User.Out)
async def patch(user_id: int, user: User.Patch) -> User.Out:
    db[user_id] = User(**{**db[user_id].dict(), **user.dict(exclude_unset=True)})
    return db[user_id]


@app.patch("/users", response_model=List[User.Out])
async def patch_many(users: List[User.PatchMany]) -> List[User.Out]:
    for user in users:
        db[user.id] = User(**{**db[user.id].dict(), **user.dict(exclude_unset=True)})
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
    assert response.status_code == 200
    assert response.json() == {
        "id": 0,
        "username": "admin",
        "groups": [{"id": 0, "name": "default"}],
    }

    # GET
    response = client.get("/users/0")
    assert response.status_code == 200
    assert response.json() == {
        "id": 0,
        "username": "admin",
        "groups": [{"id": 0, "name": "default"}],
    }

    response = client.put(
        "/users/0",
        json={
            "username": "superadmin",
            "password": "superadmin",
            "groups": [],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": 0,
        "username": "superadmin",
        "groups": [],
    }

    response = client.put(
        "/users",
        json=[
            {
                "id": 0,
                "username": "admin",
                "password": "admin",
                "groups": [{"id": 0, "name": "default", "secret": "secret_value"}],
            }
        ],
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 0,
            "username": "admin",
            "groups": [{"id": 0, "name": "default"}],
        }
    ]

    response = client.patch("/users/0", json={"id": 0, "username": "guest"})
    assert response.status_code == 200
    assert response.json() == {
        "id": 0,
        "username": "guest",
        "groups": [{"id": 0, "name": "default"}],
    }

    response = client.patch("/users", json=[{"id": 0, "groups": []}])
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 0,
            "username": "guest",
            "groups": [],
        }
    ]
