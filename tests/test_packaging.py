"""
The packaged app only contains what electron-builder.yml lists. A Python package missing from that list works in
development and silently disappears from the installer (the companion once did), because the backend imports its
optional parts inside try/except. This keeps the list and the code in step.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOT_SHIPPED = {"tests", "scripts", "tools", "evals", "docs", "learning", "localdocs", "venv", "node_modules", "installer",
               "python-dist", "dist", "dist-electron", "dist-installer", "seven_data", "data", "renders", "assets",
               "frontend", "electron", "__pycache__", "web", "knowledge", "chrome_extension", "task_panel"}


def _shipped() -> str:
    with open(os.path.join(ROOT, "electron-builder.yml"), encoding="utf-8") as f:
        return f.read()


class Packaging(unittest.TestCase):
    def test_every_python_package_the_app_imports_is_in_the_installer(self):
        listed = _shipped()
        packages = {d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d)) and d not in NOT_SHIPPED
                    and not d.startswith(".") and any(n.endswith(".py") for n in os.listdir(os.path.join(ROOT, d)))}
        missing = sorted(p for p in packages if f'"{p}/**/*"' not in listed)
        self.assertEqual(missing, [], f"folders with Python code that the installer would leave out: {missing}")

    def test_the_companion_ships(self):
        self.assertIn('"companion/**/*"', _shipped())


if __name__ == "__main__":
    unittest.main()
