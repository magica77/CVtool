import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import analysis, contains, jd_terms, tailor, validate
from documents import NS, blocks, export_docx, export_html, extract, verify_docx
from resume import make_package, new_directory


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "examples/profile.json").read_text())
        self.jd = (ROOT / "examples/job.txt").read_text()

    def draft(self, **kwargs):
        return tailor(self.profile, self.jd, "Principal Data Platform Engineer", "Meridian Labs", **kwargs)

    def test_selection_preserves_claims_and_source(self):
        original = copy.deepcopy(self.profile)
        result = self.draft(max_bullets=3)
        self.assertEqual(self.profile, original)
        self.assertEqual(result["source_profile"], original)
        self.assertEqual(result["resume"]["experience"][0]["title"], original["experience"][0]["title"])
        for source, selected in zip(original["experience"], result["resume"]["experience"]):
            self.assertLessEqual(len(selected["bullets"]), 3)
            for bullet in selected["bullets"]:
                self.assertIn(bullet, source["bullets"])
        self.assertEqual(analysis(result)["changed_claims"], [])

    def test_different_jobs_prioritize_different_bullets(self):
        infrastructure = tailor(self.profile, "Terraform", "Engineer", "Example", 1)
        streaming = tailor(self.profile, "Kafka Spark streaming", "Engineer", "Example", 1)
        self.assertEqual(infrastructure["resume"]["experience"][0]["bullets"][0]["id"], "northstar-5")
        self.assertEqual(streaming["resume"]["experience"][0]["bullets"][0]["id"], "northstar-1")

    def test_alias_and_boundary_matching(self):
        self.assertIn("AWS", jd_terms("Amazon Web Services"))
        self.assertNotIn("SQL", jd_terms("NoSQL"))
        self.assertNotIn("Java", jd_terms("JavaScript"))
        self.assertEqual(jd_terms("C++ C# .NET"), ["C++", "C#", ".NET"])
        self.assertTrue(contains("data\n  quality", "data quality"))
        self.assertFalse(contains("C++", "C"))

    def test_unknown_term_supported_and_missing_flagged(self):
        result = tailor(self.profile, "Rust and Kafka", "Engineer", "Example", extra=["Rust"])
        rows = {r["term"]: r for r in analysis(result)["terms"]}
        self.assertEqual(rows["Rust"]["status"], "not evidenced")
        self.assertEqual(rows["Kafka"]["status"], "included")
        self.assertNotIn("Rust", result["resume"]["skills"])
        with self.assertRaises(ValueError):
            jd_terms("Kafka", ["Rust"])
        self.assertIn("SQL performance", jd_terms("SQL performance", ["SQL performance"]))

    def test_invalid_draft_fails_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            for invalid in ([], {"version": 1, "target": []}):
                with self.assertRaises(ValueError):
                    make_package(invalid, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_alias_only_draft_rerenders(self):
        result = tailor(self.profile, "Amazon Web Services", "Engineer", "Example")
        with tempfile.TemporaryDirectory() as directory:
            make_package(result, Path(directory))
        self.assertFalse(analysis(result)["terms"][0]["exact_phrase"])

    def test_omitted_evidence_distinct_from_missing(self):
        self.jd += "\nExperience with deployment reviews."
        result = self.draft(max_bullets=1, extra=["deployment reviews"])
        rows = {r["term"]: r for r in analysis(result)["terms"]}
        self.assertEqual(rows["deployment reviews"]["status"], "available but omitted")
        self.assertEqual(rows["Iceberg"]["status"], "not evidenced")

    def test_unrelated_skills_do_not_count_as_experience(self):
        self.profile["skills"].append("Kubernetes")
        row = next(r for r in analysis(self.draft())["terms"] if r["term"] == "Kubernetes")
        self.assertEqual(row["status"], "included")
        self.assertEqual(row["experience_evidence"], [])

    def test_edits_flag_metrics_titles_and_new_skills(self):
        result = self.draft()
        result["resume"]["experience"][0]["bullets"][0]["text"] += " Saved $99 million."
        result["resume"]["experience"][0]["title"] = "CTO"
        result["resume"]["skills"].append("Rust")
        self.assertEqual(len(analysis(result)["changed_claims"]), 3)

    def test_invalid_profiles_fail(self):
        for mutation in (lambda p: p.update(name=""),
                         lambda p: p["experience"][0].update(start="2022-13"),
                         lambda p: p["experience"][0].update(start="2025-01", end="2024-01"),
                         lambda p: p["experience"][0]["bullets"][0].update(id="northstar"),
                         lambda p: p.update(skills="Python")):
            with self.subTest(mutation=mutation):
                p = copy.deepcopy(self.profile)
                mutation(p)
                with self.assertRaises(ValueError):
                    validate(p)
        with self.assertRaises(ValueError):
            self.draft(max_bullets=0)

    def test_reverse_chronology(self):
        self.profile["experience"].reverse()
        self.assertEqual(self.draft()["resume"]["experience"][0]["id"], "northstar")

    def test_html_escapes_candidate_content(self):
        self.profile["name"] = '<script>alert("x")</script>'
        output = export_html(blocks(self.draft()))
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)

    def test_docx_unicode_and_reading_order(self):
        self.profile["name"] = "Zoë García 李"
        items = blocks(self.draft())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            export_docx(items, path)
            self.assertTrue(verify_docx(items, path)["docx_text_roundtrip"])
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    ET.fromstring(archive.read(name))
                root = ET.fromstring(archive.read("word/document.xml"))
                self.assertEqual(root.findall(".//w:tbl", NS), [])
                self.assertEqual(root.findall(".//w:headerReference", NS), [])
                self.assertIn("Zoë García 李", extract(path))

    def test_package_complete_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "v1"
            new_directory(out, lambda p: make_package(self.draft(), p))
            self.assertTrue((out / "resume.docx").exists())
            self.assertTrue((out / "review.md").exists())
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "draft_needs_human_review")
            with self.assertRaises(ValueError):
                new_directory(out, lambda p: None)

    def test_failed_export_leaves_no_partial_package(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "v1"
            def fail(path):
                (path / "partial.txt").write_text("partial")
                raise ValueError("failed")
            with self.assertRaises(ValueError):
                new_directory(out, fail)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_prepare_cli_creates_blank_not_fictional_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "prepared"
            result = subprocess.run([sys.executable, str(ROOT / "resume.py"), "prepare", "--source",
                                     str(ROOT / "examples/job.txt"), "--out", str(out)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((out / "profile.json").read_text())["name"], "")
            self.assertTrue((out / "source.txt").exists())

    def test_cli_bad_json_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{not json}")
            result = subprocess.run([sys.executable, str(ROOT / "resume.py"), "validate", "--profile", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
