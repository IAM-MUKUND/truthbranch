"""
Pytest configuration and global fixtures for TruthBranch test suite.
"""
import pytest
from backend.app.db import get_falkordb
from backend.app.services.meta import set_meta_active_dataset


@pytest.fixture(autouse=True)
def ensure_lumen_active_dataset():
    """Ensure every test runs with the default Lumen dataset active."""
    set_meta_active_dataset(dataset_id="lumen", graph_name="kb_main")
    yield
    set_meta_active_dataset(dataset_id="lumen", graph_name="kb_main")
