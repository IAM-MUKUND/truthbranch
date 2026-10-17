from falkordb import FalkorDB
from backend.app.config import get_settings


def get_falkordb() -> FalkorDB:
    settings = get_settings()
    return FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)


def get_active_dataset_id() -> str:
    try:
        from backend.app.services.meta import get_meta_active_dataset
        d_id, _ = get_meta_active_dataset()
        return d_id
    except Exception:
        return "lumen"


def get_active_graph_name() -> str:
    try:
        from backend.app.services.meta import get_meta_active_dataset
        _, g_name = get_meta_active_dataset()
        return g_name
    except Exception:
        return "kb_main"


def get_graph(name: str = "kb_main"):
    client = get_falkordb()
    if name == "kb_main":
        name = get_active_graph_name()
    return client.select_graph(name)


def ping_falkordb() -> bool:
    try:
        client = get_falkordb()
        client.list_graphs()
        return True
    except Exception:
        return False
