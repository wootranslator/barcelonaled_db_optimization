import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """
    Se ejecuta tras la instalación inicial.
    Aseguramos que el cron existe y activamos las optimizaciones por defecto.
    """
    # 1. Activar parámetros por defecto
    params = [
        ('barcelonaled_db_optimization.opt_index_stock', 'True'),
        ('barcelonaled_db_optimization.opt_index_accounting', 'True'),
        ('barcelonaled_db_optimization.opt_index_sale', 'True'),
        ('barcelonaled_db_optimization.opt_index_technical', 'True'),
    ]
    for key, value in params:
        env['ir.config_parameter'].sudo().set_param(key, value)

    # 2. Crear el Cron si no existe (manualmente en código para evitar problemas de ref XML)
    cron_exists = env['ir.cron'].sudo().search([('name', '=', 'DB Optimization: Mantenimiento de Índices')], limit=1)
    if not cron_exists:
        try:
            model_id = env['ir.model'].sudo().search([('model', '=', 'db.optimization')], limit=1).id
            if model_id:
                env['ir.cron'].sudo().create({
                    'name': 'DB Optimization: Mantenimiento de Índices',
                    'model_id': model_id,
                    'state': 'code',
                    'code': 'model._db_optimization_maintenance()',
                    'interval_number': 1,
                    'interval_type': 'weeks',
                    'numbercall': -1,
                    'active': True,
                })
        except Exception as e:
            _logger.warning(f"No se pudo crear el cron de optimización: {e}")

    # 3. Ejecutar la optimización inicial
    try:
        env['db.optimization']._db_optimization_maintenance()
    except Exception as e:
        _logger.warning(f"Error en la optimización inicial pos-instalación: {e}")

def uninstall_hook(env):
    """
    Al desinstalar, borramos todo a menos que se indique lo contrario.
    """
    get_param = env['ir.config_parameter'].sudo().get_param
    keep_indices = get_param('barcelonaled_db_optimization.keep_indices_on_uninstall')

    if keep_indices:
        _logger.info("Desinstalación: Los índices se mantienen por configuración de usuario.")
        return

    # Llamamos a una limpieza desactivando todo
    try:
        groups = ['opt_index_stock', 'opt_index_accounting', 'opt_index_sale', 'opt_index_contact', 'opt_index_technical']
        for group in groups:
            env['ir.config_parameter'].sudo().set_param(f'barcelonaled_db_optimization.{group}', 'False')
        
        env['db.optimization']._db_optimization_maintenance()
    except Exception as e:
        _logger.warning(f"Error limpiando índices al desinstalar: {e}")
