from . import models
from . import hooks

def post_init_hook(env):
    hooks.post_init_hook(env)

def uninstall_hook(env):
    hooks.uninstall_hook(env)
