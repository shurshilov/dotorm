from ..model import Model


def build_sql_update_from_schema(
    sql: str, payload: Model, id=None, fields=[], exclude=set()
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
        payload_no_relation = payload.json(
            include=fields, exclude_none=True, exclude=exclude, only_store=True
        )
    else:
        payload_no_relation = payload.json(
            exclude=payload.get_none_update_fields_set().union(exclude),
            exclude_none=True,
            only_store=True,
        )
    fields_list, values_list = zip(*payload_no_relation.items())
    if id:
        values_list += (id,)

    query_placeholders = ", ".join([field + "=%s" for field in fields_list])
    sql = sql % (query_placeholders, "%s" if id else "")
    return sql, values_list


def build_sql_create_from_schema(
    sql: str, payload: Model, fields=[]
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
        payload_no_relation = payload.json(
            include=fields, exclude_none=True, only_store=True
        )
    else:
        payload_no_relation = payload.json(
            exclude=payload.get_none_update_fields_set(),
            exclude_none=True,
            only_store=True,
        )

    fields_list, values_list = zip(*payload_no_relation.items())

    query_columns = ", ".join(fields_list)
    query_placeholders = ", ".join(["%s"] * len(values_list))
    sql = sql % (query_columns, query_placeholders)
    return sql, values_list
