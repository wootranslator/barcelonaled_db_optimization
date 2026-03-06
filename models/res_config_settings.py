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

    # Logs for Status Monitor
    optimization_log_ids = fields.Many2many(
        'db.optimization.log', 
        string="Logs de Optimización",
        compute='_compute_log_ids'
    )

    def _compute_log_ids(self):
        # Seleccionamos los últimos 50 logs directamente
        logs = self.env['db.optimization.log'].search([], limit=50, order='id desc')
        for record in self:
            record.optimization_log_ids = [(6, 0, logs.ids)]

    @api.depends('company_id')
    def _compute_optimization_cron_id(self):
        cron = self.env.ref('barcelonaled_db_optimization.ir_cron_db_optimization_maintenance', raise_if_not_found=False)
        if not cron:
            cron = self.env['ir.cron'].sudo().search([('name', '=', 'DB Optimization: Mantenimiento de Índices')], limit=1)
        for record in self:
            record.optimization_cron_id = cron

    def action_apply_db_optimizations(self):
        """Ejecución en segundo plano"""
        self.env['db.optimization']._db_optimization_maintenance()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Proceso Iniciado',
                'message': 'La optimización se está ejecutando en segundo plano. Pulsa "Actualizar Monitor" para ver el progreso.',
                'type': 'info',
                'sticky': False,
            }
        }

    def action_reindex_db_tables(self):
        """Ejecución en segundo plano de reindexado"""
        self.env['db.optimization']._db_optimization_maintenance(force_reindex=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reindexado Iniciado',
                'message': 'La reconstrucción de índices ha comenzado en segundo plano (operación lenta). Pulsa "Actualizar Monitor" constantemente.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_refresh_optimization_logs(self):
        """Refresca los logs en la vista"""
        self._compute_log_ids()
        # Retornar True suele ser suficiente si el campo es Many2many y se cambia en vals, 
        # pero retornamos un reload para mayor seguridad en res.config.settings.
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
