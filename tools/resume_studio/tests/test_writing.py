import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import tailor
from resume import make_package
from writing import writing_review


class WritingTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "examples/profile.json").read_text())

    def test_flags_specific_cues_without_rewriting_facts(self):
        self.profile["summary"] = ["Results-driven engineer who leveraged Python. The platform was improved by the team."]
        original = copy.deepcopy(self.profile)
        result = writing_review(self.profile)
        kinds = {f["kind"] for f in result["findings"]}
        self.assertIn("formulaic_wording", kinds)
        self.assertIn("possible_passive", kinds)
        self.assertEqual(self.profile, original)
        self.assertIsNone(result["success_probability"])

    def test_long_sentence_flag_does_not_count_skill_lists(self):
        self.profile["summary"] = [" ".join(["word"] * 26) + "."]
        self.profile["skills"] = [" ".join(["skill"] * 40)]
        result = writing_review(self.profile)
        self.assertEqual(result["sentences_over_25_words"], 1)
        self.assertEqual(result["longest_sentence_words"], 26)

    def test_sentence_guide_is_per_sentence_not_per_bullet(self):
        self.profile["summary"] = [" ".join(["Built"] + ["systems"] * 19) + ". " +
                                   " ".join(["Reduced"] + ["costs"] * 19) + "."]
        self.assertEqual(writing_review(self.profile)["sentences_over_25_words"], 0)

    def test_technical_names_not_blanket_banned(self):
        self.profile["summary"] = ["Built Kafka pipelines on Amazon Web Services with change data capture (CDC)."]
        result = writing_review(self.profile)
        self.assertFalse([f for f in result["findings"] if f["id"] == "summary:1"])

    def test_generated_package_has_style_guidance_and_pending_review(self):
        draft = tailor(self.profile, "Python SQL", "Principal Engineer", "Example")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            make_package(draft, path)
            result = json.loads((path / "writing-review.json").read_text())
            self.assertEqual(result["independent_review_status"], "pending")
            self.assertIn("ASD-STE100", (path / "editing-prompt.md").read_text())
            self.assertIn("ATS", (path / "reviewer-prompt.md").read_text())
            self.assertIn("Writing review", (path / "review.md").read_text())
            self.assertEqual(json.loads((path / "draft.json").read_text())["source_profile"], self.profile)


if __name__ == "__main__":
    unittest.main()
