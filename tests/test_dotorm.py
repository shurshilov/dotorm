import unittest
import datetime
from typing import Any

from dotorm.orm import DotModel
from dotorm.fields import Boolean, Char, Integer, Many2many, One2one


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

    users_ids: Any = Many2many(
        store=False,
        relation_table=User,
        many2many_table="messageuser",
        column1="userid",
        column2="messageid",
    )

    message_attributes_id: Any | None = One2one(
        store=False,
        relation_table=MessageAttribute,
        relation_table_field="message_id",
    )


# async def main():
#     msg = Message(id=5, language="ru")

#     query = await msg.build_delete()
#     print(query)
#     query = await Message.build_create(msg)
#     print(query)
#     query = await msg.build_update(msg)
#     print(query)


class TestStuff(unittest.IsolatedAsyncioTestCase):
    def test_relation_fields(self):
        fields_relation = Message.get_relation_fields()
        print(fields_relation)
        self.assertEqual(len(fields_relation), 2)

    def test_store_fields(self):
        store_fields = Message.get_store_fields_dict()
        print(store_fields)
        print(Message.get_store_fields())
        self.assertEqual(len(store_fields), 15)

    def test_none_update_fields(self):
        none_update_fields = Message.get_update_fields_set()
        print(none_update_fields)
        self.assertEqual(len(none_update_fields), 3)

    def test_to_dict(self):
        msg = Message(id=5, language="ru")
        origin_dict = {
            "date": None,
            "subject": "",
            "publish": False,
            "id": 5,
            "template_id": None,
            "chain_id": None,
            "language": "ru",
            "body_json": "{}",
            "body": "",
            "body_telegram_json": "{}",
            "body_telegram": "",
            "clientid": None,
            "show_in_account": None,
            "send_email": None,
            "send_telegram": None,
        }
        res_dict = msg.to_dict()
        print(res_dict)
        self.assertEqual(res_dict, origin_dict)

    async def test_builder_get(self):
        query = await Message.build_get(5)
        self.assertEqual(
            query[0],
            "            SELECT date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram,clientid,show_in_account,send_email,send_telegram            FROM message            WHERE id = %s            LIMIT 1        ",
        )

    async def test_builder_get_with_fields(self):
        query = await Message.build_get(5, ["id", "date"])
        self.assertEqual(
            query[0],
            "            SELECT id,date            FROM message            WHERE id = %s            LIMIT 1        ",
        )

    async def test_builder_build_delete(self):
        msg = Message(id=5, language="ru")
        query = await msg.build_delete()
        self.assertEqual(
            query[0],
            "DELETE FROM message WHERE id=%s",
        )

    async def test_builder_build_create(self):
        msg = Message(id=5, language="ru")
        query = await Message.build_create(msg)
        self.assertEqual(
            query[0],
            """\n            INSERT INTO message (subject, publish, language, body_json, body, body_telegram_json, body_telegram)\n            VALUES (%s, %s, %s, %s, %s, %s, %s);\n        """,
        )

    async def test_builder_build_update(self):
        msg = Message(id=5, language="ru")
        msg_new = Message(id=5, language="en")
        query = await msg.build_update(msg_new)
        self.assertEqual(
            query[0],
            """\n            UPDATE message\n            SET subject=%s, publish=%s, language=%s, body_json=%s, body=%s, body_telegram_json=%s, body_telegram=%s\n            WHERE id = %s\n        """,
        )
        self.assertEqual(query[1], ("", False, "en", "{}", "", "{}", "", 5))

    async def test_builder_build_search(self):
        query = await Message.build_search(filter={"id": 5})
        self.assertEqual(
            query[0],
            """\n            select date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram,clientid,show_in_account,send_email,send_telegram\n            from message\n            WHERE id = %s\n            ORDER BY id DESC\n        """,
        )
        query = await Message.build_search(fields="id,date")
        self.assertEqual(
            query[0],
            """\n            select id,date\n            from message\n            \n            ORDER BY id DESC\n        """,
        )
        query = await Message.build_search(filter={"id": [1, 2, 3]})
        self.assertEqual(
            query[0],
            """\n            select date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram,clientid,show_in_account,send_email,send_telegram\n            from message\n            WHERE id in (%s, %s, %s)\n            ORDER BY id DESC\n        """,
        )

    async def test_builder_build_table_len(self):
        query = await Message.build_table_len()
        self.assertEqual(
            query[0],
            "SELECT COUNT(*) FROM message",
        )

    # async def test_builder_build_update_one2one(self):
    #     query = await Message.build_update_one2one()
    #     self.assertEqual(
    #         query[0],
    #         "SELECT COUNT(*) FROM message",
    #     )

    # async def test_builder_build_create_one2one(self):
    #     query = await Message.build_create_one2one()
    #     self.assertEqual(
    #         query[0],
    #         "SELECT COUNT(*) FROM message",
    #     )

    # async def test_builder_build_get_with_relations(self):
    #     query = await Message.build_get_with_relations()
    #     self.assertEqual(
    #         query[0],
    #         "SELECT COUNT(*) FROM message",
    #     )

    # async def test_builder_build_update_with_relations(self):
    #     query = await Message.build_update_with_relations()
    #     self.assertEqual(
    #         query[0],
    #         "SELECT COUNT(*) FROM message",
    #     )

    # async def test_builder_build_create_with_relations(self):
    #     query = await Message.build_create_with_relations()
    #     self.assertEqual(
    #         query[0],
    #         "SELECT COUNT(*) FROM message",
    #     )
