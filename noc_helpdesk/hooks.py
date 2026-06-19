def post_init_hook(cr, registry):
    try:
        # 1. Limpa tags dos tickets específicos
        cr.execute(
            """
            DELETE FROM helpdesk_ticket_helpdesk_ticket_tag_rel
            WHERE helpdesk_ticket_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN ('helpdesk_ticket_3',
                'helpdesk_ticket_6', 'helpdesk_ticket_7')
                AND model = 'helpdesk.ticket'
            )
        """
        )

        # 2. Atualiza stage dos tickets 4 e 5 para 'New'
        cr.execute(
            """
            SELECT res_id FROM ir_model_data
            WHERE module = 'helpdesk_mgmt'
            AND name = 'helpdesk_ticket_stage_new'
            AND model = 'helpdesk.ticket.stage'
        """
        )
        stage = cr.fetchone()
        if stage:
            cr.execute(
                """
                UPDATE helpdesk_ticket SET stage_id = %s
                WHERE id IN (
                    SELECT res_id FROM ir_model_data
                    WHERE module = 'helpdesk_mgmt'
                    AND name IN ('helpdesk_ticket_4', 'helpdesk_ticket_5')
                    AND model = 'helpdesk.ticket'
                )
            """,
                (stage[0],),
            )

        # 3. Remove FK dos tickets nos stages a deletar
        cr.execute(
            """
            UPDATE helpdesk_ticket SET stage_id = NULL
            WHERE stage_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN (
                    'helpdesk_ticket_stage_in_progress',
                    'helpdesk_ticket_stage_awaiting',
                    'helpdesk_ticket_stage_cancelled',
                    'helpdesk_ticket_stage_rejected'
                )
                AND model = 'helpdesk.ticket.stage'
            )
        """
        )

        # 4. Deleta os stages
        cr.execute(
            """
            DELETE FROM helpdesk_ticket_stage
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN (
                    'helpdesk_ticket_stage_in_progress',
                    'helpdesk_ticket_stage_awaiting',
                    'helpdesk_ticket_stage_cancelled',
                    'helpdesk_ticket_stage_rejected'
                )
                AND model = 'helpdesk.ticket.stage'
            )
        """
        )

        # 1. Remove FK dos tickets que referenciam as categorias
        cr.execute(
            """
            UPDATE helpdesk_ticket SET category_id = NULL
            WHERE category_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN
                ('helpdesk_category_1', 'helpdesk_category_2',
                'helpdesk_category_3')
                AND model = 'helpdesk.ticket.category'
            )
        """
        )

        # 2. Deleta as categorias
        cr.execute(
            """
            DELETE FROM helpdesk_ticket_category
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN
                ('helpdesk_category_1', 'helpdesk_category_2',
                'helpdesk_category_3')
                AND model = 'helpdesk.ticket.category'
            )
        """
        )

        # 5. Limpa FK das tags a deletar
        cr.execute(
            """
            DELETE FROM helpdesk_ticket_helpdesk_ticket_tag_rel
            WHERE helpdesk_ticket_tag_id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN ('helpdesk_tag_1', 'helpdesk_tag_2',
                'helpdesk_tag_3')
                AND model = 'helpdesk.ticket.tag'
            )
        """
        )

        # 6. Deleta as tags
        cr.execute(
            """
            DELETE FROM helpdesk_ticket_tag
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'helpdesk_mgmt'
                AND name IN ('helpdesk_tag_1', 'helpdesk_tag_2',
                'helpdesk_tag_3')
                AND model = 'helpdesk.ticket.tag'
            )
        """
        )

    except Exception:
        raise
