import json
from pathlib import Path
import unittest


class NarrativeEvaluationFixtureTests(unittest.TestCase):
    def test_narrative_evaluation_fixture_has_ten_sanitized_cases(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config" / "evals" / "narrative.v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload.get("cases") if isinstance(payload, dict) else None
        self.assertIsInstance(cases, list)
        self.assertGreaterEqual(len(cases), 10)
        ids = set()
        for case in cases:
            self.assertIsInstance(case, dict)
            case_id = str(case.get("id") or "")
            self.assertTrue(case_id)
            self.assertNotIn(case_id, ids)
            ids.add(case_id)
            self.assertIsInstance(case.get("input"), dict)
            self.assertIsInstance(case.get("assertions"), dict)
            serialized = json.dumps(case, ensure_ascii=False).lower()
            self.assertNotIn("sk-", serialized)
            self.assertNotIn("access_token", serialized)
            self.assertNotIn("session_cookie", serialized)


if __name__ == "__main__":
    unittest.main()
