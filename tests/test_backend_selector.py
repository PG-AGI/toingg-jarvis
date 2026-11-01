import unittest
from unittest.mock import MagicMock, patch

from backend_selector import get_backend_name, maybe_register_pipecat_tools

class BackendSelectorTest(unittest.IsolatedAsyncioTestCase):
    @patch("backend_selector._config", {"BACKEND": "toingg"})
    def test_default_backend_is_toingg(self):
        self.assertEqual(get_backend_name(), "toingg")

    @patch("backend_selector._config", {"BACKEND": "pipecat_gemini"})
    def test_pipecat_backend_is_recognized(self):
        self.assertEqual(get_backend_name(), "pipecat_gemini")

    @patch("backend_selector._config", {"BACKEND": "pipecat_gemini"})
    def test_registers_tools_when_pipecat_selected(self):
        mock_llm = MagicMock()
        # ``register_launcher_tools`` is imported from ``pipecat_gemini_tools``;
        # we patch it to verify it is called without executing real Pipecat code.
        with patch("backend_selector.register_launcher_tools") as mock_register:
            maybe_register_pipecat_tools(mock_llm)
            mock_register.assert_called_once_with(mock_llm)

    @patch("backend_selector._config", {"BACKEND": "toingg"})
    def test_no_registration_when_toingg(self):
        mock_llm = MagicMock()
        with patch("backend_selector.register_launcher_tools") as mock_register:
            maybe_register_pipecat_tools(mock_llm)
            mock_register.assert_not_called()

if __name__ == "__main__":
    unittest.main()
