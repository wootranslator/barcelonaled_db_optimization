import logging
import time
import threading
from odoo import models, api, fields, registry

_logger = logging.getLogger(__name__)

def run_optimization_in_thread(db_name, force_reindex, user_id):
    """Función para ejecutar la optimización en un hilo secundario con su propia conexión"""
    with registry(db_name).cursor() as cr:
        env = api.Environment(cr, user_id, {})
        log_model = env['db.optimization.log']
        get_param = env['ir.config_parameter'].sudo().get_param

        # 1. Definir los grupos (idéntico al anterior)
        optimization_groups = {
            'stock': {
                'label': 'Inventario',
                'enabled': get_param('barcelonaled_db_optimization.opt_index_stock') == 'True',
                'indexes': [
                    ("stock_picking", "stock_picking__priority_scheduled_date_id_idx", 
                     "(company_id, priority DESC, scheduled_date ASC, id DESC)"),
                    ("stock_move", "stock_move__company_seq_id_idx", 
                     "(company_id, sequence, id)"),
                    ("stock_update", "stock_update__product_id_idx", 
                     "(product_id)"),
                    ("stock_valuation_layer", "stock_valuation_layer__product_company_include_value_qty_idx", 
                     "(product_id, company_id) INCLUDE (value, quantity)"),
                ]
            },
            'accounting': {
                'label': 'Contabilidad',
                'enabled': get_param('barcelonaled_db_optimization.opt_index_accounting') == 'True',
                'indexes': [
                    ("account_edi_document", "account_edi_document__state_index", "(state)"),
                    ("account_edi_document", "account_edi_document__blocking_level_index", 
                     "(blocking_level) WHERE blocking_level IS NOT NULL"),
                ]
            },
            'sale': {
                'label': 'Ventas / TPV',
                'enabled': get_param('barcelonaled_db_optimization.opt_index_sale') == 'True',
                'indexes': [
                    ("pos_order_line", "pos_order_line__sale_order_origin_id_index", 
                     "(sale_order_origin_id) WHERE sale_order_origin_id IS NOT NULL"),
                ]
            },
            'contact': {
                'label': 'Contactos',
                'enabled': get_param('barcelonaled_db_optimization.opt_index_contact') == 'True',
                'indexes': [
                    ("res_partner", "res_partner__customer_supplier_rank_index", "(customer_rank, supplier_rank)"),
                ]
            },
            'technical': {
                'label': 'Técnico / Core',
                'enabled': get_param('barcelonaled_db_optimization.opt_index_technical') == 'True',
                'indexes': [
                    ("mail_message_reaction", "mail_message_reaction__message_id_index", "(message_id)"),
                    ("ir_logging", "ir_logging__level_type_index", "(level, type)"),
                    ("ir_module_module_dependency", "ir_module_module_dependency__module_id_index", "(module_id)"),
                ]
            }
        }

        # 2. Limpiar logs y empezar
        log_model.sudo().search([]).unlink()
        cr.commit()
        
        mode_str = "REINDEX" if force_reindex else "MANTENIMIENTO"
        log_model.add_log(f"🚀 Iniciando {mode_str} en segundo plano...", 'info')
        cr.commit()

        total_indexes = sum(len(g['indexes']) for g in optimization_groups.values() if g['enabled'])
        current_idx = 0

        for group_name, data in optimization_groups.items():
            if data['enabled']:
                log_model.add_log(f"📦 Grupo: {data['label']}", 'info')
                cr.commit()
                for table, index_name, definition in data['indexes']:
                    current_idx += 1
                    try:
                        # Asegurar índice
                        query = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} ON {table} {definition};"
                        cr.execute(query)
                        cr.commit()
                        
                        if force_reindex:
                            log_model.add_log(f"🔄 [{current_idx}/{total_indexes}] Reindexando {index_name}...", 'info')
                            cr.commit()
                            start_time = time.time()
                            cr.execute(f"REINDEX INDEX CONCURRENTLY {index_name};")
                            cr.commit()
                            duration = round(time.time() - start_time, 2)
                            log_model.add_log(f"✅ {index_name} listo ({duration}s)", 'success')
                            cr.commit()
                        else:
                            log_model.add_log(f"✓ {index_name} verificado", 'info')
                            cr.commit()

                    except Exception as e:
                        cr.rollback()
                        log_model.add_log(f"❌ Error en {index_name}: {str(e)}", 'error')
                        cr.commit()
            else:
                # Borrar si está desactivado
                for table, index_name, definition in data['indexes']:
                    try:
                        cr.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};")
                        cr.commit()
                    except:
                        cr.rollback()

        log_model.add_log("🏁 Tarea finalizada.", 'success')
        cr.commit()

class DbOptimization(models.Model):
    _name = 'db.optimization'
    _description = 'Mantenimiento de Optimización de DB'

    @api.model
    def _db_optimization_maintenance(self, force_reindex=False):
        """Lanza el hilo de optimización para no bloquear la UI y permitir CONCURRENTLY"""
        thread = threading.Thread(target=run_optimization_in_thread, args=(self.env.cr.dbname, force_reindex, self.env.uid))
        thread.start()
        return True

class DbOptimizationLog(models.Model):
    _name = 'db.optimization.log'
    _description = 'Logs de Optimización de DB'
    _order = 'id desc'

    message = fields.Text(string="Mensaje")
    type = fields.Selection([
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
        ('success', 'Éxito')
    ], string="Tipo", default='info')
    
    @api.model
    def add_log(self, message, log_type='info'):
        self.create({'message': message, 'type': log_type})
