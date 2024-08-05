from .crud import BuilderCRUD
from .many2many import BuilderMany2many
from ..fields import Field, Many2many, Many2one, One2many, One2one


class BuilderCRUDRelashions(BuilderCRUD, BuilderMany2many):
    # TODO: join instead select
    @classmethod
    async def build_get_with_relations(
        cls, id, fields=[], relation_fields=[]
    ) -> tuple[list, list, list]:
        request_list = []
        field_name_list = []
        field_list = []

        request_list.append(await cls.build_get(id, fields))

        if not relation_fields:
            relation_fields = cls.get_relation_fields()
        else:
            # проверка что поля действительно relaton, можно убрать
            relation_fields = [
                (name, field)
                for name, field in cls.get_relation_fields()
                if name in relation_fields
            ]

        for name, field in relation_fields:
            if isinstance(field, Field):
                relation = field.relation or False
                if not relation:
                    continue
                relation_table = field.relation_table
                relation_table_field = field.relation_table_field
            else:
                continue

            if isinstance(field, Many2many):
                field_name_list.append(name)
                field_list.append(field)
                request_list.append(
                    await cls.build_get_many2many(
                        id,
                        relation_table,
                        field.many2many_table,
                        field.column1,
                        field.column2,
                    )
                )
            elif isinstance(field, One2many):
                field_name_list.append(name)
                field_list.append(field)
                request_list.append(
                    await relation_table.build_search(filter={relation_table_field: id})
                )
            elif isinstance(field, One2one):
                field_name_list.append(name)
                field_list.append(field)
                request_list.append(
                    # await cls.build_get_one2one(
                    #     relation_table, relation_table_field, id
                    # )
                    await relation_table.build_search(
                        filter={relation_table_field: id},
                        limit=1,
                    )
                )
            elif isinstance(field, Many2one):
                field_name_list.append(name)
                field_list.append(field)
                request_list.append(await relation_table.build_get(id))

        return request_list, field_name_list, field_list

    async def build_update_with_relations(self, payload=None, fields=[]):
        request_list = []
        field_list = []
        if not payload:
            payload = self
        # Создание сущности в базе без связей
        request_list.append(await self.build_update(payload, self.id, fields))

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
                field_list.append(field)
                for obj in field_obj:
                    request_list.append(
                        await obj.build_update_one2one(
                            fk_id=payload.id, fk=relation_table_field
                        )
                    )
            elif isinstance(field, One2one):
                field_list.append(field)
                request_list.append(
                    await field_obj.build_update_one2one(
                        fk_id=payload.id, fk=relation_table_field
                    )
                )
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
