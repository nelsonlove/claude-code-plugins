import os
import pytest

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary PIM data directory."""
    os.environ["PIM_DATA_DIR"] = str(tmp_path)
    yield tmp_path
    del os.environ["PIM_DATA_DIR"]
