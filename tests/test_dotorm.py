import unittest
import datetime

from dotorm.orm import DotModel
from dotorm.fields import Boolean, Char, Datetime, Integer, Many2many, One2one, Char


class MessageAttribute(DotModel):
    __table__ = "message_attributes"
    __route__ = "/message_attributes"

    id: int = Integer(primary_key=True)
    date_create: datetime.datetime | None = Datetime(default=None)
    publish_date: datetime.datetime | None = Datetime(default=None)
    message_id: int = Integer(default=None)
    is_deleted: bool | None = Boolean(default=None)
    is_draft: bool | None = Boolean(default=None)
    show_in_account: bool = Boolean()
    send_email: bool = Boolean()
    send_telegram: bool = Boolean()


class User(DotModel):
    __table__ = "user"

    id: int = Integer(primary_key=True)
    clientid: int | None = Integer(default=None)
    name: str = Char(max_length=255)
    email: str = Char(max_length=255)
    languageid: str | None = Char(default=None, max_length=255)
    agree_to_get_notifications: str | None = Char(default=None, max_length=255)
    event_type_id: str | None = Char(default=None, max_length=255)
    telegram_id: int | None = Integer(default=None)

    selected: bool | None = Boolean(default=None)
    client_name: str | None = Char(default=None, max_length=255)
    region_id: str | None = Char(default=None, max_length=255)
    vip_status: str | None = Char(default=None, max_length=255)
    notification_status: str | None = Char(default=None, max_length=255)
    id_and_name: str | None = Char(default=None, max_length=255)
    partner_id: int | None = Integer(default=None)
    has_partner: str | None = Char(default=None, max_length=255)


class Message(DotModel):
    __table__ = "message"
    __route__ = "/notifications"

    date: datetime.datetime | None = Datetime(default=None)
    subject: str | None = Char(default="", max_length=255)
    publish: bool | None = Boolean(default=False)
    id: int = Integer(primary_key=True)
    template_id: int | None = Integer(default=None)
    chain_id: int | None = Integer(default=None)
    language: str | None = Char(default=None, max_length=255)
    body_json: str | None = Char(default="{}", max_length=255)
    body: str | None = Char(default="", max_length=255)
    body_telegram_json: str | None = Char(default="{}", max_length=255)
    body_telegram: str | None = Char(default="", max_length=255)

    clientid: int | None = Integer(store=False, default=None)
    show_in_account: bool | None = Boolean(store=False, default=None)
    send_email: bool | None = Boolean(store=False, default=None)
    send_telegram: bool | None = Boolean(store=False, default=None)

    users_ids: list[User] = Many2many(
        store=False,
        relation_table=User,
        many2many_table="messageuser",
        column1="userid",
        column2="messageid",
    )

    message_attributes_id: MessageAttribute | None = One2one(
        store=False,
        relation_table=MessageAttribute,
        relation_table_field="message_id",
    )


class TestBuilder(unittest.IsolatedAsyncioTestCase):
    def test_all_fields(self):
        fields_all = Message.get_fields()
        print(fields_all)
        self.assertEqual(len(fields_all), 17)

    def test_relation_fields(self):
        fields_relation = Message.get_relation_fields()
        print(fields_relation)
        self.assertEqual(len(fields_relation), 2)

    def test_none_update_fields(self):
        none_update_fields = Message.get_none_update_fields_set()
        print(none_update_fields)
        self.assertEqual(len(none_update_fields), 7)

    def test_store_fields(self):
        store_fields = Message.get_store_fields()
        print(store_fields)
        self.assertEqual(len(store_fields), 11)
        self.assertEqual(type(store_fields), list)

    def test_store_fields_dict(self):
        store_fields = Message.get_store_fields_dict()
        print(store_fields)
        self.assertEqual(len(store_fields), 11)
        self.assertEqual(type(store_fields), dict)

    def test_get_store_fields_json(self):
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
        }
        res_dict = msg.json(only_store=True)
        print(res_dict)
        self.assertEqual(res_dict, origin_dict)

    async def test_builder_get(self):
        query = await Message.build_get(5)
        self.assertEqual(
            query[0],
            "SELECT date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram FROM message WHERE id = %s LIMIT 1",
        )

    async def test_builder_get_with_fields(self):
        query = await Message.build_get(5, ["id", "date"])
        self.assertEqual(
            query[0],
            "SELECT id,date FROM message WHERE id = %s LIMIT 1",
        )

    async def test_builder_build_delete(self):
        msg = Message(id=5, language="ru")
        query = await msg.build_delete(msg.id)
        self.assertEqual(
            query[0],
            "DELETE FROM message WHERE id=%s",
        )

    async def test_builder_build_create(self):
        msg = Message(id=5, language="ru")
        query = await Message.build_create(msg)
        self.assertEqual(
            query[0],
            """INSERT INTO message (subject, publish, language, body_json, body, body_telegram_json, body_telegram) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        )

    async def test_builder_build_update(self):
        msg = Message(id=5, language="ru")
        msg_new = Message(id=5, language="en")
        query = await msg.build_update(msg_new, msg_new.id)
        self.assertEqual(
            query[0],
            """UPDATE message SET subject=%s, publish=%s, language=%s, body_json=%s, body=%s, body_telegram_json=%s, body_telegram=%s WHERE id = %s""",
        )
        self.assertEqual(query[1], ("", False, "en", "{}", "", "{}", "", 5))

    async def test_builder_build_search(self):
        query = await Message.build_search(filter={"id": 5})
        self.assertEqual(
            query[0],
            """select date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram from message WHERE id = %s ORDER BY id DESC """,
        )
        query = await Message.build_search(fields=["id", "date"])
        self.assertEqual(
            query[0],
            """select id,date from message  ORDER BY id DESC """,
        )
        query = await Message.build_search(filter={"id": [1, 2, 3]})
        self.assertEqual(
            query[0],
            """select date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram from message WHERE id in (%s, %s, %s) ORDER BY id DESC """,
        )

    async def test_builder_build_table_len(self):
        query = await Message.build_table_len()
        self.assertEqual(
            query[0],
            "SELECT COUNT(*) FROM message",
        )

    async def test_builder_build_update_one2one(self):
        msg_attr = MessageAttribute(id=5, show_in_account=True)
        query = await msg_attr.build_update_one2one(fk_id=100, fk="message_id")
        self.assertEqual(
            query[0],
            "UPDATE message_attributes SET show_in_account=%s WHERE message_id = %s",
        )

    async def test_builder_build_create_one2one(self):
        msg_attr = MessageAttribute(id=5, show_in_account=True)
        query = await msg_attr.build_create_one2one(fk_id=100, fk="message_id")
        self.assertEqual(
            query[0],
            "INSERT INTO message_attributes (message_id, show_in_account) VALUES (%s, %s)",
        )

    async def test_builder_build_get_with_relations(self):
        query = await Message.build_get_with_relations(
            100, relation_fields=["message_attributes_id"]
        )
        self.assertEqual(
            query[0][0][0],
            "SELECT date,subject,publish,id,template_id,chain_id,language,body_json,body,body_telegram_json,body_telegram FROM message WHERE id = %s LIMIT 1",
        )

        self.assertEqual(
            query[0][1][0],
            "select id,date_create,publish_date,message_id,is_deleted,is_draft,show_in_account,send_email,send_telegram from message_attributes WHERE message_id = %s ORDER BY id DESC LIMIT %s",
        )

    async def test_builder_build_update_with_relations(self):
        msg = Message(id=5, language="ru")
        msg_attr = MessageAttribute(id=5, show_in_account=True)
        msg.message_attributes_id = msg_attr
        query, field_list = await msg.build_update_with_relations()
        self.assertEqual(
            query[0][0],
            """\
UPDATE message \
SET subject=%s, publish=%s, language=%s, body_json=%s, body=%s, body_telegram_json=%s, body_telegram=%s \
WHERE id = %s""",
        )
        self.assertEqual(
            query[1][0],
            """\
UPDATE message_attributes \
SET show_in_account=%s \
WHERE message_id = %s""",
        )

    async def test_builder_build_create_with_relations(self):
        msg = Message(id=5, language="ru")
        msg_attr = MessageAttribute(id=5, show_in_account=True)
        msg.message_attributes_id = msg_attr
        query = await Message.build_create_with_relations(msg)
        self.assertEqual(
            query[0][0],
            """INSERT INTO message (subject, publish, language, body_json, body, body_telegram_json, body_telegram) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        )
        self.assertEqual(
            query[1][0],
            """\
INSERT INTO message_attributes (message_id, show_in_account) \
VALUES (%s, %s)""",
        )
