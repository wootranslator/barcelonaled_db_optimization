from odoo import fields, models, api
from datetime import datetime

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

    # HTML Terminal for better UI reliability
    optimization_terminal = fields.Html(
        string="Terminal de Optimización",
        compute='_compute_optimization_terminal',
        sanitize=False
    )

    def _compute_optimization_terminal(self):
        logs = self.env['db.optimization.log'].search([], limit=20, order='id desc')
        html_content = '<div style="font-family: monospace; font-size: 11px; line-height: 1.4;">'
        if not logs:
            html_content += '<div style="color: #666; text-align: center; margin-top: 50px;">--- No hay logs recientes ---</div>'
        else:
            for log in logs:
                color = "#fff"
                if log.type == 'success': color = "#28a745"
                elif log.type == 'error': color = "#dc3545"
                elif log.type == 'warning': color = "#ffc107"
                elif log.type == 'info': color = "#17a2b8"
                
                time_str = log.create_date.strftime('%H:%M:%S') if log.create_date else '--:--:--'
                # Escapar mensajes o asegurar que no rompan el HTML
                msg = log.message.replace('\n', '<br/>')
                html_content += f'<div style="margin-bottom: 4px;"><span style="color: #888;">[{time_str}]</span> <span style="color: {color};">{msg}</span></div>'
        html_content += '</div>'
        for record in self:
            record.optimization_terminal = html_content

    @api.depends('company_id')
    def _compute_optimization_cron_id(self):
        cron = self.env.ref('barcelonaled_db_optimization.ir_cron_db_optimization_maintenance', raise_if_not_found=False)
        if not cron:
            cron = self.env['ir.cron'].sudo().search([('name', '=', 'DB Optimization: Mantenimiento de Índices')], limit=1)
        for record in self:
            record.optimization_cron_id = cron

    def action_apply_db_optimizations(self):
        self.env['db.optimization']._db_optimization_maintenance()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Comando Enviado',
                'message': 'Optimización lanzada. Dale a refrescar en el monitor.',
                'type': 'info',
            }
        }

    def action_reindex_db_tables(self):
        self.env['db.optimization']._db_optimization_maintenance(force_reindex=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reindexado Iniciado',
                'message': 'Operación pesada en curso. Vigila el monitor.',
                'type': 'warning',
            }
        }

    def action_refresh_optimization_logs(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
