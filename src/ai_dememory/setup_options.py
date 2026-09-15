"""Explicit setup extras; the default setup never imports integrations."""

from .config import load_config, save_config
from .modules import enable_module


def install_extras(vault, *, codex=False, schedule=False, scope=None, hours=None):
    result = {}
    if codex:
        from .integration_install import install_user
        before = load_config()
        try:
            enable_module("harness-codex")
            result["codex"] = install_user(vault)
        except Exception:
            save_config(before)
            raise
        enable_module("workbench")
    if schedule:
        from .scheduled import manage_task
        from .settings import load_settings, save_settings
        before, settings_before = load_config(), load_settings(vault)
        settings = load_settings(vault)
        settings["schedule"]["enabled"] = True
        if scope is not None:
            settings["schedule"]["scope"] = scope
        if hours is not None:
            settings["schedule"]["interval_hours"] = hours
        try:
            save_settings(vault, settings)
            enable_module("workbench")
            task = manage_task(vault, "install")
        except Exception:
            save_settings(vault, settings_before)
            save_config(before)
            raise
        result["consolidation"] = {**task, "schedule": settings["schedule"],
                                   "history_ingestion": False, "resident_worker": False}
    return result
