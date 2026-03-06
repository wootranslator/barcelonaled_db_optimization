import logging
import time
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class DbOptimization(models.Model):
    _name = 'db.optimization'
    _description = 'Mantenimiento de Optimización de DB'

    @api.model
    def _db_optimization_maintenance(self, force_reindex=False):
        """
        Método central para gestionar la creación, eliminación y mantenimiento de los índices.
        Organizado por Apps de Odoo.
        """
        get_param = self.env['ir.config_parameter'].sudo().get_param
        # Usamos un cursor nuevo para los logs para que no afecten a la transacción principal
        # y así poder guardar el estado incluso si hay fallos.
        log_model = self.env['db.optimization.log']

        # Mapeo de grupos a queries e índices
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

        # Limpiar logs anteriores
        log_model.sudo().search([]).unlink()
        
        # IMPORTANTE: Liberar la transacción actual. 
        # CREATE INDEX CONCURRENTLY no puede ejecutarse dentro de un bloque BEGIN/COMMIT.
        self.env.cr.commit()

        if force_reindex:
            log_model.add_log("🚀 Iniciando REINDEX CONCURRENTLY general...", 'info')

        total_indexes = sum(len(g['indexes']) for g in optimization_groups.values() if g['enabled'])
        current_index = 0

        for group_name, data in optimization_groups.items():
            if data['enabled']:
                log_model.add_log(f"📦 Procesando grupo: {data['label']}", 'info')
                for table, index_name, definition in data['indexes']:
                    current_index += 1
                    try:
                        # 1. Asegurar índice (CONCURRENTLY requiere estar fuera de transacción)
                        query = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} ON {table} {definition};"
                        _logger.info(f"DB OPT: Ejecutando {query}")
                        self.env.cr.execute(query)
                        # Commit inmediato para liberar el lock y confirmar la creación
                        self.env.cr.commit()
                        
                        if force_reindex:
                            msg = f"🔄 [{current_index}/{total_indexes}] Reindexando {index_name}..."
                            log_model.add_log(msg, 'info')
                            start_time = time.time()
                            
                            self.env.cr.execute(f"REINDEX INDEX CONCURRENTLY {index_name};")
                            self.env.cr.commit()
                            
                            duration = round(time.time() - start_time, 2)
                            log_model.add_log(f"✅ {index_name} finalizado en {duration}s", 'success')
                        else:
                            log_model.add_log(f"✓ Índice {index_name} verificado/creado", 'info')
                            
                    except Exception as e:
                        # Si algo falla, el cursor queda en estado "Aborted", hay que hacer rollback para poder seguir
                        self.env.cr.rollback()
                        err_msg = f"❌ Error en {index_name}: {str(e)}"
                        _logger.warning(f"DB OPT: {err_msg}")
                        # Intentar loguear el error (ahora que el cursor está limpio tras el rollback)
                        try:
                            log_model.add_log(err_msg, 'error')
                        except:
                            pass
            else:
                for table, index_name, definition in data['indexes']:
                    try:
                        self.env.cr.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};")
                        self.env.cr.commit()
                    except:
                        self.env.cr.rollback()

        if force_reindex:
            log_model.add_log("🏁 Tarea de mantenimiento finalizada satisfactoriamente.", 'success')

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
        # Forzamos una transacción independiente para cada log para que sea visible en tiempo real
        self.create({'message': message, 'type': log_type})
        self.env.cr.commit()
