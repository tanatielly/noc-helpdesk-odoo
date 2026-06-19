def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE helpdesk_ticket
            ADD COLUMN IF NOT EXISTS last_user_uid   integer,
            ADD COLUMN IF NOT EXISTS last_user_date  timestamp without time zone
        """
    )
