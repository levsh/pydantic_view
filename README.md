# Pydantic view helper decorator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

### Installation
```bash
pip install pydantic_view
```

### Usage

```python
In [1]: from pydantic import BaseModel, Field
   ...: from pydantic_view import view
   ...: 
   ...: 
   ...: class User(BaseModel):
   ...:     id: int
   ...:     username: str
   ...:     password: str
   ...:     address: str
   ...: 
   ...: @view("Create", exclude={"id"})
   ...: class UserCreate(User):
   ...:     pass
   ...:
   ...: @view("Update")
   ...: class UserUpdate(User):
   ...:     pass
   ...:
   ...: @view("Patch")
   ...: class UserPatch(User):
   ...:     username: str = None
   ...:     password: str = None
   ...:     address: str = None
   ...:
   ...: @view("Out", exclude={"password"})
   ...: class UserOut(User):
   ...:     pass

In [2]: user = User(id=0, username="human", password="iamaman", address="Earth")
   ...: user.Out()
   ...: 
Out[2]: UserOut(id=0, username='human', address='Earth')

In [3]: User.Update(id=0, username="human", password="iamasuperman", address="Earth")
   ...: 
Out[3]: UserUpdate(id=0, username='human', password='iamasuperman', address='Earth')

In [4]: User.Patch(id=0, address="Mars")
   ...: 
Out[4]: UserPatch(id=0, username=None, password=None, address='Mars')
```


### FastAPI example

```python
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from pydantic_view import view, view_field_validator


class UserSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public: Optional[str] = None
    secret: Optional[str] = None


@view("Out", exclude={"secret"})
class UserSettingsOut(UserSettings):
    pass


@view("Create")
class UserSettingsCreate(UserSettings):
    pass


@view("Update")
class UserSettingsUpdate(UserSettings):
    pass


@view("Patch")
class UserSettingsPatch(UserSettings):
    public: str = None
    secret: str = None


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    username: str
    password: str = Field(default_factory=lambda: "password")
    settings: UserSettings

    @view_field_validator({"Create", "Update", "Patch"}, "username")
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError
        return v


@view("Out", exclude={"password"})
class UserOut(User):
    pass


@view("Create", exclude={"id"})
class UserCreate(User):
    settings: UserSettings = Field(default_factory=UserSettings)


@view("Update", exclude={"id"})
class UserUpdate(User):
    pass


@view("Patch", exclude={"id"})
class UserPatch(User):
    username: str = None
    password: str = None
    settings: UserSettings = None


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


@app.patch("/users/{user_id}", response_model=User.Out)
async def patch(user_id: int, user: User.Patch) -> User.Out:
    db[user_id] = User(**{**db[user_id].model_dump(), **user.model_dump(exclude_unset=True)})
    return db[user_id]


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
```
