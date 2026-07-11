from unittest.mock import MagicMock
import pytest
from studio.god_session import GodSession


@pytest.fixture
def fake_session():
    writer = MagicMock()
    writer.status.return_value = {"constitution": True, "tilemap": False}
    return GodSession(god=MagicMock(), writer=writer)
