import asyncio
import datetime

from dotorm.orm import DotModel
from dotorm.fields import Boolean, Char, Integer, Many2many, One2many, One2one


class MessageAttribute(DotModel):
    __table__ = "message_attributes"
    __route__ = "/message_attributes"

    id: int | None = Integer(primary_key=True, default=None)
    date_create: datetime.datetime | None = None
    publish_date: datetime.datetime | None = None
    # = Field(relation="many2one", relation_table=Message)
    message_id: int = Integer(default=None)
    is_deleted: bool | None = None
    is_draft: bool | None = None
    show_in_account: bool = Boolean()
    send_email: bool = Boolean()
    send_telegram: bool = Boolean()


class User(DotModel):
    __table__ = "user"

    id: int = Integer(primary_key=True)
    clientid: int | None = None
    name: str = Char(max_length=255)
    email: str = Char(max_length=255)
    languageid: str | None = None
    agree_to_get_notifications: str | None = None
    event_type_id: str | None = None
    telegram_id: int | None = None

    selected: bool | None = None
    client_name: str | None = None
    region_id: str | None = None
    vip_status: str | None = None
    notification_status: str | None = None
    id_and_name: str | None = None
    partner_id: int | None = None
    has_partner: str | None = None


class Message(DotModel):
    __table__ = "message"
    __route__ = "/notifications"

    date: datetime.datetime | None = None
    subject: str | None = ""
    publish: bool | None = False
    id: int | None = Integer(primary_key=True, default=None)
    template_id: int | None = None
    chain_id: int | None = None
    language: str | None = None
    body_json: str | None = "{}"
    body: str | None = ""
    body_telegram_json: str | None = "{}"
    body_telegram: str | None = ""

    clientid: int | None = Integer(_store=False, default=None)
    show_in_account: bool | None = Boolean(_store=False, default=None)
    send_email: bool | None = Boolean(_store=False, default=None)
    send_telegram: bool | None = Boolean(_store=False, default=None)

    users_ids: list[MessageAttribute] = Many2many(
        store=False,
        relation_table=User,
        many2many_table="messageuser",
        column1="userid",
        column2="messageid",
    )

    message_attributes_id: MessageAttribute = One2one(
        store=False,
        relation_table=MessageAttribute,
        relation_table_field="message_id",
    )


async def main():
    msg = Message(id=5, language="ru")
    # print(msg)
    print("RELATION")
    print(Message.get_relation_fields())
    print("STORE")
    print(Message.get_store_fields())
    print(Message.get_store_fields_dict())
    print("NONE UPDATE")
    print(Message.get_update_fields_set())
    print("TO DICT")
    print(msg.to_dict())

    query = await Message.build_get(5)
    print(query)
    query = await Message.build_get(5, ["id", "date"])
    print(query)
    query = await msg.build_delete()
    print(query)
    query = await Message.build_create(msg)
    print(query)
    msg_new = Message(id=5, language="en")
    query = await msg.build_update(msg_new)
    print(query)
    query = await Message.build_search(filter={"id": 5})
    print(query)
    query = await Message.build_search(fields="id,date")
    print(query)
    query = await Message.build_search(filter={"id": [1, 2, 3]})
    print(query)
    query = await Message.build_table_len()
    print(query)
    msg_attr = MessageAttribute(id=5, show_in_account=True)
    query = await msg_attr.build_update_one2one(fk_id=100, fk="message_id")
    print(query)
    query = await msg_attr.build_create_one2one(fk_id=100, fk="message_id")
    print(query)
    query = await Message.build_get_with_relations(
        100, relation_fields=["message_attributes_id"]
    )
    print(query)


def test_answer():
    msg = Message(id=5, language="ru")
    # print(msg)
    print("RELATION")
    print(Message.get_relation_fields())
    assert 4 == 5


if __name__ == "__main__":
    asyncio.run(main())
