# Pydantic view helper decorator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

### Installation
```bash
pip install pydantic_view
```

### Usage

```python
In [1]: from uuid import UUID, uuid4
   ...: 
   ...: from pydantic import BaseModel, Field
   ...: from pydantic_view import view
   ...: 
   ...: 
   ...: @view("Create", exclude=["id"])
   ...: @view("Update")
   ...: @view("Patch", optional=["username", "password", "address"])
   ...: @view("Out", exclude=["password"])
   ...: class User(BaseModel):
   ...:     id: int
   ...:     username: str
   ...:     password: str
   ...:     address: str
   ...: 

In [2]: user = User(id=0, username="human", password="iamaman", address="Earth")
   ...: user.Out()
   ...: 
Out[2]: Out(id=0, username='human', address='Earth')

In [3]: User.Update(id=0, username="human", password="iamasuperman", address="Earth")
   ...: 
Out[3]: Update(id=0, username='human', password='iamasuperman', address='Earth')

In [4]: User.Patch(id=0, address="Mars")
   ...: 
Out[4]: Patch(id=0, username=None, password=None, address='Mars')
```
