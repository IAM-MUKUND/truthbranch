from falkordb import FalkorDB
from backend.app.config import get_settings


def get_falkordb() -> FalkorDB:
    settings = get_settings()
    return FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)


def get_graph(name: str = "kb_main"):
    client = get_falkordb()
    return client.select_graph(name)


def ping_falkordb() -> bool:
    try:
        client = get_falkordb()
        client.list_graphs()
        return True
    except Exception:
        return False
