import logging
from odoo import models, api

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
        
        # Mapeo de grupos a queries e índices
        optimization_groups = {
            'stock': {
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
                'enabled': get_param('barcelonaled_db_optimization.opt_index_accounting') == 'True',
                'indexes': [
                    ("account_edi_document", "account_edi_document__state_index", "(state)"),
                    ("account_edi_document", "account_edi_document__blocking_level_index", 
                     "(blocking_level) WHERE blocking_level IS NOT NULL"),
                ]
            },
            'sale': {
                'enabled': get_param('barcelonaled_db_optimization.opt_index_sale') == 'True',
                'indexes': [
                    ("pos_order_line", "pos_order_line__sale_order_origin_id_index", 
                     "(sale_order_origin_id) WHERE sale_order_origin_id IS NOT NULL"),
                ]
            },
            'contact': {
                'enabled': get_param('barcelonaled_db_optimization.opt_index_contact') == 'True',
                'indexes': [
                    ("res_partner", "res_partner__customer_supplier_rank_index", "(customer_rank, supplier_rank)"),
                ]
            },
            'technical': {
                'enabled': get_param('barcelonaled_db_optimization.opt_index_technical') == 'True',
                'indexes': [
                    ("mail_message_reaction", "mail_message_reaction__message_id_index", "(message_id)"),
                    ("ir_logging", "ir_logging__level_type_index", "(level, type)"),
                    ("ir_module_module_dependency", "ir_module_module_dependency__module_id_index", "(module_id)"),
                ]
            }
        }

        self.env.cr.commit()

        for group_name, data in optimization_groups.items():
            if data['enabled']:
                for table, index_name, definition in data['indexes']:
                    try:
                        query = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} ON {table} {definition};"
                        _logger.info(f"DB OPT [{group_name}]: Asegurando índice {index_name}")
                        self.env.cr.execute(query)
                        self.env.cr.commit()
                        
                        if force_reindex:
                            _logger.info(f"DB OPT [{group_name}]: Reindexando {index_name}")
                            self.env.cr.execute(f"REINDEX INDEX CONCURRENTLY {index_name};")
                            self.env.cr.commit()
                            
                    except Exception as e:
                        _logger.warning(f"DB OPT [{group_name}]: Error en {index_name}: {e}")
                        self.env.cr.rollback()
            else:
                for table, index_name, definition in data['indexes']:
                    try:
                        self.env.cr.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};")
                        self.env.cr.commit()
                    except:
                        self.env.cr.rollback()

        return True
