from .utils import RequestBuilder, RequestBuilderForm
from .crud import BuilderCRUD
from .many2many import BuilderMany2many
from ..fields import Field, Many2many, Many2one, One2many, One2one


class BuilderCRUDRelashions(BuilderCRUD, BuilderMany2many):
    @classmethod
    async def build_search_relation(
        cls,
        fields_relation: list[tuple[str, Field]],
        # start=None,
        # end=None,
        # limit=80,
        # order="ASC",
        # sort="id",
        # filter: Any = None,
        records: list = [],
    ):
        request_list: list[RequestBuilder] = []
        ids: list[int] = [record.id for record in records]
        for name, field in fields_relation:
            # field_name_list.append(name)
            # field_list.append(field)
            # if isinstance(field, Many2many):
            #     await cls.build_get_many2many(
            #             id,
            #             relation_table,
            #             field.many2many_table,
            #             field.column1,
            #             field.column2,
            #         )
            #     request_list.append()
            # TODO: если поля нет, то добавить name в питоне
            fields = ["id"]
            if field.relation_table.get_fields().get("name"):
                fields.append("name")
            if isinstance(field, One2many):
                stmt, val = await field.relation_table.build_search(
                    fields=[*fields, field.relation_table_field],
                    filter=[(field.relation_table_field, "in", ids)],
                )
                req = RequestBuilder(
                    stmt=stmt, value=val, field_name=name, field=field, fields=fields
                )
                request_list.append(req)

            elif isinstance(field, Many2many):
                stmt = await cls.build_get_many2many_multiple(
                    ids=ids,
                    relation_table=field.relation_table,
                    many2many_table=field.many2many_table,
                    column1=field.column1,
                    column2=field.column2,
                    fields=fields,
                )
                req = RequestBuilder(
                    stmt=stmt,
                    value=ids,
                    field_name=name,
                    field=field,
                )
                request_list.append(req)

            elif isinstance(field, Many2one):
                ids_m2o: list[int] = [getattr(record, name) for record in records]
                # оставляем только уникальные ид, так как в m2o несколько записей
                # могут ссылаться на одну сущность
                ids_m2o = list(set(ids_m2o))
                stmt, val = await field.relation_table.build_search(
                    fields=fields, filter=[("id", "in", ids_m2o)]
                )
                req = RequestBuilder(
                    stmt=stmt,
                    value=val,
                    field_name=name,
                    field=field,
                )
                request_list.append(req)
        return request_list

    # TODO: join instead select?
    # @classmethod
    # async def build_get_with_relations(
    #     cls, record, fields_relation: list[tuple[str, Field, list]]
    # ):
    #     request_list: list[RequestBuilderForm] = []

    #     for name, field, fields_nested in fields_relation:
    #         relation_table = field.relation_table
    #         relation_table_field = field.relation_table_field
    #         # всегда по умолчанию селектится минимум поле ид и name
    #         # name проверяется на то есть ли оно
    #         if not fields_nested:
    #             fields = ["id"]
    #             if relation_table.get_fields().get("name"):
    #                 fields.append("name")
    #         else:
    #             fields = fields_nested

    #         if isinstance(field, Many2one):
    #             # взять ид из поля many2one и запросить запись из связанной таблицы
    #             m2o_id = getattr(record, name)
    #             stmt, val = await relation_table.build_get(m2o_id, fields=fields)

    #         req = RequestBuilderForm(
    #             stmt=stmt, value=val, field_name=name, field=field, fields=fields
    #         )
    #         request_list.append(req)

    #     return request_list

    @classmethod
    async def build_update_with_relations(
        cls, payload, id, fields_relation: list[tuple[str, Many2many | One2many]] = []
    ):
        request_list = []
        field_list = []
        # TODO: обновление relations полей
        # get_relation_fields
        for name, field in fields_relation:
            relation = field.relation
            field_obj = getattr(payload, name)
            relation_table_field = field.relation_table_field

            if isinstance(field, Many2many):
                ...
                # field_obj.created
                # field_obj.selected
                # field_obj.unselected
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
                # field_obj.created
                # field_obj.deleted
                # пройтись по циклу создать запись в один запрос
                # insert into (create_bulk)
                # также с удалением delete_bulk
                field_list.append(field)
                data_created = [
                    field.relation_table(**obj) for obj in field_obj["created"]
                ]
                request_list.append(await cls.build_create_bulk(data_created))
                # for obj in field_obj:
                #     request_list.append(
                #         await obj.build_update_one2one(
                #             fk_id=payload.id, fk=relation_table_field
                #         )
                #     )
        return request_list, field_list

    @classmethod
    async def build_create_with_relations(cls, payload, id=None):
        request_list = []
        # Создание сущности в базе без связей
        request_list.append(await cls.build_create(payload))

        # TODO: обновление relations полей
        # get_relation_fields
        for field_name, field in payload.get_fields().items():
            if isinstance(field, Field):
                relation = field.relation or False
                if not relation:
                    continue
                field_obj = getattr(payload, field_name)
                relation_table_field = field.relation_table_field or False
            else:
                continue

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
                            fk_id=payload.id, fk=relation_table_field
                        )
                    )
            elif isinstance(field, One2one):
                request_list.append(
                    await field_obj.build_create_one2one(
                        fk_id=payload.id, fk=relation_table_field
                    )
                )
        return request_list
