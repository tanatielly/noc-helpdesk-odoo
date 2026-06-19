def migrate(cr, version):
    cr.execute(
        "ALTER TABLE helpdesk_ferias ADD COLUMN IF NOT EXISTS substitute_id integer"
    )
