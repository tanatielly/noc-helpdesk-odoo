def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE mail_activity
        ADD COLUMN IF NOT EXISTS date_start timestamp without time zone
        """
    )
    cr.execute(
        """CREATE INDEX IF NOT EXISTS mail_activity_date_start_index ON
        mail_activity (date_start)"""
    )
