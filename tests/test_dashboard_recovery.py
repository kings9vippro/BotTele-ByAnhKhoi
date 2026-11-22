"""Regression contracts for iPhone dashboard recovery and database handle lifecycle."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DashboardRecoveryTests(unittest.TestCase):
    def test_optional_reads_retry_only_recoverable_failures(self):
        source = (ROOT / "static" / "control.js").read_text(encoding="utf-8")
        self.assertIn("function shouldRetryDashboard(error)", source)
        self.assertIn("error?.code==='timeout'", source)
        self.assertIn("status===429||status>=500", source)
        self.assertIn("!shouldRetryDashboard(error)", source)
        self.assertIn("options.signal?.aborted", source)
        self.assertIn("jobs.map(job=>loadDashboardJob(job,options))", source)
        self.assertIn("dashboardFailureLabel(result.reason)", source)

    def test_mobile_sections_have_dock_and_safe_area_clearance(self):
        css = (ROOT / "static" / "yanbi.css").read_text(encoding="utf-8")
        self.assertIn(
            "padding-bottom:calc(120px + max(10px,env(safe-area-inset-bottom,0px)));", css
        )
        self.assertIn(
            "scroll-padding-bottom:calc(120px + max(10px,env(safe-area-inset-bottom,0px)));", css
        )

    def test_account_list_closes_storage_connection(self):
        tree = ast.parse((ROOT / "glaze_app.py").read_text(encoding="utf-8"))
        func = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "api_miniapp_accounts")
        calls = [
            node for node in ast.walk(func)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "close"
        ]
        self.assertTrue(calls, "Account GET must close the DB connection used for storage identity")


if __name__ == "__main__":
    unittest.main()
