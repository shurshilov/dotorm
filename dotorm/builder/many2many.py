from ..model import Model


class BuilderMany2many(Model):
    @classmethod
    async def build_get_many2many(
        cls, id, comodel, relation, column1, column2, fields=[]
    ):
        """Возвращает только выбранных пользователей(получателей). Для режима просмотра.
        Без администраторов"""
        # TODO: universal
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
        return cmd, [id, "KDPadmin%%"]  # , comodel.prepare_ids, "fetchall"
