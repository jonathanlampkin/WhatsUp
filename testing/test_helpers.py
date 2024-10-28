# test_helpers.py
from unittest.mock import MagicMock

def mock_sqlite_connect():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    return mock_conn, mock_cursor
