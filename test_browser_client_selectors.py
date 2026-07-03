import sys
import types
import unittest


websocket_stub = types.ModuleType("websocket")
websocket_stub.WebSocketApp = object
sys.modules.setdefault("websocket", websocket_stub)

playwright_stub = types.ModuleType("playwright")
sync_api_stub = types.ModuleType("playwright.sync_api")
sync_api_stub.sync_playwright = lambda: None
sync_api_stub.Page = object
sync_api_stub.Playwright = object
sys.modules.setdefault("playwright", playwright_stub)
sys.modules.setdefault("playwright.sync_api", sync_api_stub)

from browserClient import BrowserClient


class BrowserClientSelectorRepairTests(unittest.TestCase):
    def test_repairs_tailwind_decimal_and_multiple_classes(self):
        self.assertEqual(
            BrowserClient._repair_selector("button.p-2.5.flex"),
            'button[class~="p-2.5"][class~="flex"]',
        )

    def test_leaves_simple_and_complex_selectors_alone(self):
        self.assertEqual(BrowserClient._repair_selector("button.primary"), "button.primary")
        self.assertEqual(BrowserClient._repair_selector("button.foo, a.bar"), "button.foo, a.bar")


if __name__ == "__main__":
    unittest.main()
