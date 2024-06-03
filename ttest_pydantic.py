import datetime
from pydantic import BaseModel, Field


class Message(BaseModel):
    # __table__ = "message"
    # __route__ = "/notifications"

    date = None
    tittle: str | None = ""
    id: int | None = Field(primary_key=True, default=None)


Message()
Message(tittle="213", id=5)
# class User(BaseModel):
#     model_config = ConfigDict(
#         extra="allow",
#     )
#     id: int
#     hash: str
#     auth_date: int = None
#     first_name: str = None
#     photo_url: str = None
#     username: str = None
