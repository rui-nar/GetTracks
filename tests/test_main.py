import pytest
from main import get_greeting


class TestMain:
    def test_get_greeting(self):
        """Test that get_greeting returns the expected message."""
        result = get_greeting()
        assert result == "Hello, World!"
        assert isinstance(result, str)