import pytest
from fastapi.testclient import TestClient
from drama_factory.api import create_app

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data")) as c:
        yield c
