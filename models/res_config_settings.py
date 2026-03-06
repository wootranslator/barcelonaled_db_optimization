from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Optimization Toggles by App
    opt_index_stock = fields.Boolean(
        string="Optimizar Inventario",
        config_parameter='barcelonaled_db_optimization.opt_index_stock',
        help="Índices para stock_picking, stock_move, stock_update y valoración."
    )
    opt_index_accounting = fields.Boolean(
        string="Optimizar Contabilidad",
        config_parameter='barcelonaled_db_optimization.opt_index_accounting',
        help="Índices para account_edi_document y estados de factura."
    )
    opt_index_sale = fields.Boolean(
        string="Optimizar Ventas / TPV",
        config_parameter='barcelonaled_db_optimization.opt_index_sale',
        help="Índices para agilizar pedidos de venta y líneas de TPV."
    )
    opt_index_contact = fields.Boolean(
        string="Optimizar Contactos",
        config_parameter='barcelonaled_db_optimization.opt_index_contact',
        help="Índices para agilizar búsquedas en grandes volúmenes de contactos."
    )
    opt_index_technical = fields.Boolean(
        string="Optimizar Core (Técnico)",
        config_parameter='barcelonaled_db_optimization.opt_index_technical',
        help="Índices para mail_message_reaction, ir_logging e ir_module."
    )

    keep_indices_on_uninstall = fields.Boolean(
        string="Mantener índices tras desinstalar",
        config_parameter='barcelonaled_db_optimization.keep_indices_on_uninstall'
    )

    # Cron configuration fields
    optimization_cron_id = fields.Many2one(
        'ir.cron', 
        string="Cron de Optimización",
        compute='_compute_optimization_cron_id'
    )
    cron_interval_number = fields.Integer(related='optimization_cron_id.interval_number', readonly=False)
    cron_interval_type = fields.Selection(related='optimization_cron_id.interval_type', readonly=False)
    cron_nextcall = fields.Datetime(related='optimization_cron_id.nextcall', readonly=False)
    cron_lastcall = fields.Datetime(related='optimization_cron_id.lastcall', readonly=True)
    cron_active = fields.Boolean(related='optimization_cron_id.active', readonly=False)

    # Logs for Terminal UI
    optimization_log_ids = fields.Many2many(
        'db.optimization.log', 
        string="Logs de Optimización",
        compute='_compute_log_ids'
    )

    def _compute_log_ids(self):
        logs = self.env['db.optimization.log'].search([], limit=10, order='id desc')
        for record in self:
            record.optimization_log_ids = logs

    @api.depends('company_id')
    def _compute_optimization_cron_id(self):
        cron = self.env.ref('barcelonaled_db_optimization.ir_cron_db_optimization_maintenance', raise_if_not_found=False)
        if not cron:
            # Fallback searching by name if the XML ID is lost or not yet created
            cron = self.env['ir.cron'].sudo().search([('name', '=', 'DB Optimization: Mantenimiento de Índices')], limit=1)
        for record in self:
            record.optimization_cron_id = cron

    def action_apply_db_optimizations(self):
        """Ejecución manual para aplicar los índices seleccionados con mensaje de confirmación"""
        self.env['db.optimization']._db_optimization_maintenance()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Optimización Completada',
                'message': 'Se han procesado los índices correctamente. Revisa el terminal de logs.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_reindex_db_tables(self):
        """Ejecución manual de REINDEX CONCURRENTLY en las tablas afectadas con mensaje de confirmación"""
        self.env['db.optimization']._db_optimization_maintenance(force_reindex=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reindexado Finalizado',
                'message': 'La reconstrucción de índices ha finalizado. Consulta los logs para detalles de tiempo.',
                'type': 'success',
                'sticky': True,
            }
        }
