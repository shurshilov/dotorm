import datetime
from typing import Self
from .exceptions import OrmUpdateEmptyParamsException
from .fields import Many2many, Many2one, One2many, One2one
from .model import Model


# T = TypeVar("T", bound=Model)


# class class_or_instancemethod(classmethod):
#     """Этот класс нужен для определения метод вызван в контексте класса или инстанса
#     другими словами @classmethod или @instancemethod
#     """

#     def __get__(self, instance, type_):
#         descr_get = super().__get__ if instance is None else self.__func__.__get__
#         return descr_get(instance, type_)


class Builder(Model):
    """Своя реализация ORM. Пока что так называемая one-way ORM. Чем то похоже на Mayim.
    1. На момент написания данного кода не одна orm система не поддерживала
    асинхронную работу в режиме продакшена. В sql алхимии данная функция также
    была в режиме beta.
    2. В реализации АПИ-сервера уже были написаны все необходимые запросы и
    переписывать их на orm заняло бы какое то время. Вместо этого они были просто
    скопированы и использованы.
    3. В первоначальном виде предполагалась работа с одной моделью в режиме CRUD
    и с 2 на чтение, что также придавало нецелесообразности использования готового ORM.
    4. В процессе разработки были добавлены несколько моделей и появились предпосылки к
    использованию orm,для лучше организации кода и уменьшения количества дублирующего кода.
    5. Из-за пункта 1 было принято решенние временно реализовать собственный класс, и в дальнейшем
    при появлении стабильных версий асинхронных orm использовать их.
    """

    _CACHE_DATA: dict = {}
    _CACHE_LAST_TIME: dict = {}

    @staticmethod
    def cache(name, ttl=30):
        """Реализация простого кеша на TTL секунд, таблиц которые редко меняются,
        и делать запрос в БД не целесообразно каждый раз, можно сохранить результат.
        При использовании более одного воркера необходимо использовать redis.

        Arguments:
            name -- name cache store data
            ttl -- seconds cache store
        """

        def decorator(func):
            async def wrapper(self, *args):
                # если данные есть в кеше
                if self._CACHE_DATA.get(name):
                    time_diff = datetime.datetime.now() - self._CACHE_LAST_TIME[name]
                    # проверить актуальные ли они
                    if time_diff.seconds < ttl:
                        # если актуальные вернуть их
                        return self._CACHE_DATA[name]

                # если данных нет или они не актуальные сделать запрос в БД и запомнить
                self._CACHE_DATA[name] = await func(self, *args)
                # также сохранить дату и время запроса, для последующей проверки
                self._CACHE_LAST_TIME[name] = datetime.datetime.now()
                return self._CACHE_DATA[name]

            return wrapper

        return decorator

    @classmethod
    def build_sql_update_from_schema(
        cls, sql: str, payload: Self, id=None, fields=[], exclude=set()
    ) -> tuple[str, list]:
        """Составляет запрос создания (insert).
        Исключает поля primary_key (id), relation_fields, non-stored fields

        Arguments:
            sql -- текст шаблона запроса
            payload -- обьект модели пидантика

        Returns:
            sql -- текст запроса с подстановками (биндингами)
            values_list -- значения для биндинга
        """
        if fields:
            payload_no_relation = payload.to_dict(
                include=fields, exclude_none=True, exclude=exclude
            )
        else:
            payload_no_relation = payload.to_dict(
                exclude=cls.get_update_fields_set().union(exclude), exclude_none=True
            )
        fields_list, values_list = zip(*payload_no_relation.items())
        if id:
            values_list += (id,)

        query_placeholders = ", ".join([field + "=%s" for field in fields_list])
        sql = sql % (query_placeholders, "%s" if id else "")
        return sql, values_list

    @classmethod
    def build_sql_create_from_schema(
        cls, sql: str, payload: Self, fields=[]
    ) -> tuple[str, list]:
        """Составляет запрос обновления (update).
        Исключает поля primary_key (id), relation_fields, non-stored fields

        Arguments:
            sql -- текст шаблона запроса
            payload -- обьект модели пидантика

        Returns:
            sql -- текст запроса с подстановками (биндингами)
            values_list -- значения для биндинга
        """
        if fields:
            payload_no_relation = payload.to_dict(include=fields, exclude_none=True)
        else:
            payload_no_relation = payload.to_dict(
                exclude=cls.get_update_fields_set(), exclude_none=True
            )

        fields_list, values_list = zip(*payload_no_relation.items())

        query_columns = ", ".join(fields_list)
        query_placeholders = ", ".join(["%s"] * len(values_list))
        sql = sql % (query_columns, query_placeholders)
        return sql, values_list

    ##################
    # QUERY BULDER
    ##################

    # CRUD
    @classmethod
    async def build_get(cls, id, fields=[]):
        if not fields:
            fields = cls.get_store_fields()
        else:
            fields = ",".join(fields)
        stmt = f"""
            SELECT {fields}
            FROM {cls.__table__}
            WHERE id = %s
            LIMIT 1
        """.replace(
            "\n", ""
        )

        return stmt, [id], cls.prepare_id, "fetchall"

    async def build_delete(self):
        stmt = f"DELETE FROM {self.__table__} WHERE id=%s"

        return stmt, self.id, None, "fetchall"

    @classmethod
    async def build_create(cls, payload):
        stmt = f"""
            INSERT INTO {cls.__table__} (%s)
            VALUES (%s);
        """
        # TODO: создание relations полей
        stmt, values_list = cls.build_sql_create_from_schema(stmt, payload)
        return stmt, values_list, None, "lastrowid"

    async def build_update(self, payload: Self, fields=[]):
        # self_or_cls: Self
        # если вызов из инстанса, ане из класса
        # if not isinstance(self_or_cls, type):
        #     id = self_or_cls.id
        #     payload = self_or_cls

        # if not payload:
        #     raise OrmUpdateEmptyParamsException

        stmt = f"""
            UPDATE {self.__table__}
            SET %s
            WHERE id = %s
        """
        # Создание сущности в базе без связей
        stmt, values_list = self.build_sql_update_from_schema(
            stmt, payload, self.id, fields
        )
        return stmt, values_list, None, "fetchall"

    @classmethod
    async def build_search(
        cls,
        start=None,
        end=None,
        limit=None,
        order="DESC",
        sort="id",
        filter=None,
        fields=[],
        raw=None,
    ):
        if not fields:
            fields = cls.get_store_fields()
        else:
            fields = fields
        where = ""
        where_values = ()
        if filter:
            # фильтруем только те поля, которые есть в модели
            # для текста like, для списка in, для остальных =
            fields_store = cls.get_store_fields_dict()
            fields_store_keys = fields_store.keys()

            where_condition = []
            for key, value in filter.items():
                if key in fields_store_keys:
                    # TODO: поддержка всех операций
                    if type(value) == list:
                        # SQL IN
                        list_condition = [str(field) for field in value]
                        query_placeholders = ", ".join(["%s"] * len(list_condition))
                        where_condition.append(f"{key} in (%s)" % query_placeholders)
                        where_values += tuple(list_condition)
                    elif type(fields_store[key]) == str:
                        # SQL LIKE
                        where_condition.append(f"{key} like %s")
                        # экранирующий процент, чтобы добавить один процент в строку,
                        # чтобы поиск был в любой части строки %%
                        where_values += ("%%" + value + "%%",)
                    else:
                        # SQL =
                        where_condition.append(f"{key} = %s")
                        where_values += (str(value),)
            where = "WHERE " + " and ".join(where_condition)

        cmd = f"""
            select {fields}
            from {cls.__table__}
            {where}
            ORDER BY {sort} {order}
        """
        if end != None and start != None:
            cmd += "LIMIT %s, %s"
            val = (start, end - start)
        elif limit:
            cmd += "LIMIT %s"
            val = (limit,)
        else:
            val = tuple()

        if where_values:
            val = where_values + val
        return cmd, val, cls.prepare_ids if not raw else None, "fetchall"

    @classmethod
    async def build_table_len(cls):
        cmd = f"SELECT COUNT(*) FROM {cls.__table__}"
        return cmd, None, lambda rows: [r["COUNT(*)"] for r in rows], "fetchall"

    async def build_update_one2one(self, fk_id: int, fields=[], fk="id"):
        if not fk_id:
            raise OrmUpdateEmptyParamsException

        stmt = f"""
            UPDATE {self.__table__}
            SET %s
            WHERE {fk} = %s
        """

        stmt, values_list = self.build_sql_update_from_schema(
            stmt, self, fk_id, fields, exclude={fk}
        )
        return stmt, values_list, None, "fetchall"

    async def build_create_one2one(self, fk_id=id, fk="id"):
        if not fk_id:
            raise OrmUpdateEmptyParamsException

        stmt = f"""
            INSERT INTO {self.__table__} (%s)
            VALUES (%s)
        """
        # TODO: создание relations полей
        setattr(self, fk, fk_id)
        # self[fk] = fk_id
        stmt, values_list = self.build_sql_create_from_schema(stmt, self)
        return stmt, values_list, None, "lastrowid"

    # TODO: universal
    @classmethod
    async def build_get_many2many(
        cls, id, comodel, relation, column1, column2, fields=[]
    ):
        """Возвращает только выбранных пользователей(получателей). Для режима просмотра.
        Без администраторов"""
        cmd = f"""
        SELECT p.id, p.clientid, p.name, p.email,
        IF(p.languageId=1,'Russian','English') as languageid,
        IF(p.agree_to_get_notifications=1,'Yes','No') as agree_to_get_notifications,
        -- IF(ns.event_type_id=6,'Yes','No') as event_type_id,
        IF(MAX(ns.is_checked) = 1 AND event_type_id = 6 AND agree_to_get_notifications = 1, 'Yes', 'No') as event_type_id,
        p.telegram_id

        FROM {comodel.__table__} p
        JOIN {relation} pt ON p.id = pt.{column1}
        JOIN {cls.__table__} t ON pt.{column2} = t.id

        LEFT JOIN notification_settings ns
        ON ns.user_id = p.id  AND ns.event_type_id = 6

        WHERE
            t.id = %s and p.isdeleted = 0 and p.is_blocked = 0 and p.name NOT LIKE %s
        GROUP BY p.id
        ORDER BY p.clientid DESC
        """
        return cmd, (id,) + ("KDPadmin%%",), comodel.prepare_ids, "fetchall"

    @classmethod
    async def build_get_with_relations(
        cls, id, fields=[], relation_fields=[]
    ) -> tuple[list, list]:
        request_list = []
        field_name_list = []

        request_list.append(await cls.build_get(id, fields))

        if not relation_fields:
            relation_fields = cls.get_relation_fields()
        else:
            relation_fields = [
                (name, field)
                for name, field in cls.get_relation_fields()
                if name in relation_fields
            ]

        for name, field in relation_fields:
            relation = field.relation or False
            relation_table = field.relation_table or None
            relation_table_field = field.relation_table_field or None

            if isinstance(field, Many2many):
                field_name_list.append(name)
                request_list.append(
                    await self_or_cls.build_get_many2many(
                        id,
                        relation_table,
                        field.many2many_table or False,
                        field.column1 or False,
                        field.column2 or False,
                    )
                ),
            elif isinstance(field, One2many):
                field_name_list.append(name)
                request_list.append(
                    await relation_table.build_search(filter={relation_table_field: id})
                )
            elif isinstance(field, One2one):
                field_name_list.append(name)
                request_list.append(
                    await relation_table.build_search(
                        filter={relation_table_field: id},
                        limit=1,
                    )
                )
            elif isinstance(field, Many2one):
                field_name_list.append(name)
                request_list.append(await relation_table.build_get(id))

        return request_list, field_name_list
        # results = await asyncio.gather(*request_list)
        # # добавляем атрибуты к исходному обьекту,
        # # получая удобное обращение через дот-нотацию
        # record: self_or_cls = results.pop(0)
        # for field in results:
        #     setattr(record, field_name_list.pop(0), field)

        # return record

    async def build_update_with_relations(self, payload=None, fields=[]):
        request_list = []
        if not payload:
            payload = self
        # если вызов из инстанса, ане из класса
        # if not isinstance(self_or_cls, type):
        #     id = self_or_cls.id
        #     payload = self_or_cls
        # Создание сущности в базе без связей
        request_list.append(await self.build_update(payload, fields))

        # TODO: обновление relations полей
        # get_relation_fields
        for field_name, field_obj in payload.get_fields().items():
            field = self.get_field(field_name)
            relation = field.relation or False
            if not relation:
                continue
            relation_table_field = field.relation_table_field or False

            if isinstance(field, Many2many):
                ...
                # обновление каждой записи в many2many
                # for obj in field_obj:
                #     cmd = f"""
                #         UPDATE {relation_table.__table__}
                #         SET %s
                #         WHERE id = {obj.id}
                #     """
                #     sql, values_list = self_or_cls.build_sql_update_from_schema(cmd, obj)
                #     request_list.append(self_or_cls.execute_sql_fetchall(cmd, values_list))
            elif isinstance(field, One2many):
                # обновление каждой записи в one2many
                for obj in field_obj:
                    request_list.append(
                        await obj.build_update_one2one(
                            fk_id=id, fk=relation_table_field
                        )
                    )
            elif isinstance(field, One2one):
                request_list.append(
                    await field_obj.build_update_one2one(
                        fk_id=id, fk=relation_table_field
                    )
                )
        return request_list
        # results = await asyncio.gather(*request_list)
        # return results

    @classmethod
    async def build_create_with_relations(cls, payload, id=None):
        request_list = []
        # Создание сущности в базе без связей
        request_list.append(await cls.build_create(payload))

        # TODO: обновление relations полей
        # get_relation_fields
        for field_name, field_obj in payload:
            field = cls.get_field(field_name)
            relation = field.relation or False
            if not relation:
                continue
            # relation_table = field.get("relation_table", False)
            relation_table_field = field.relation_table_field or False

            if isinstance(field, Many2many):
                ...
                # обновление каждой записи в many2many
                # for obj in field_obj:
                #     cmd = f"""
                #         UPDATE {relation_table.__table__}
                #         SET %s
                #         WHERE id = {obj.id}
                #     """
                #     sql, values_list = self_or_cls.build_sql_update_from_schema(cmd, obj)
                #     request_list.append(self_or_cls.execute_sql_fetchall(cmd, values_list))
            elif isinstance(field, One2many):
                # обновление каждой записи в one2many
                for obj in field_obj:
                    request_list.append(
                        await obj.build_create_one2one(
                            fk_id=id, fk=relation_table_field
                        )
                    )
            elif isinstance(field, One2one):
                request_list.append(
                    await field_obj.build_create_one2one(
                        fk_id=id, fk=relation_table_field
                    )
                )
        return request_list
        # results = await asyncio.gather(*request_list)
        # return results
