{
    'name': 'Barcelonaled DB Optimization',
    'version': '1.0',
    'summary': 'Optimizaciones de base de datos personalizadas para mejorar rendimiento.',
    'description': '''
        Se instalan índices de PostgreSQL diseñados a medida para
        cuellos de botella específicos (ej. stock_picking, account_edi, mail).
        Al desinstalar el módulo, se retiran los índices limítrofes, 
        a menos que se especifique lo contrario en Ajustes Generales.
    ''',
    'category': 'Technical',
    'author': 'Antigravity',
    'depends': ['base', 'base_setup', 'stock', 'account_edi', 'mail', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
