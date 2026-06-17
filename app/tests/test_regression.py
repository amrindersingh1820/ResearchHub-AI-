import unittest
import json
from app.utils.text_helpers import ensure_text

class MockDocument:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}

class TestRegression(unittest.TestCase):
    def test_ensure_text_none(self):
        self.assertEqual(ensure_text(None), "")

    def test_ensure_text_string(self):
        self.assertEqual(ensure_text("hello"), "hello")

    def test_ensure_text_list_of_strings(self):
        self.assertEqual(ensure_text(["page1", "page2"]), "page1\npage2")

    def test_ensure_text_nested_list(self):
        self.assertEqual(ensure_text(["a", ["b", "c"], None]), "a\nb\nc\n")

    def test_ensure_text_dict(self):
        data = {"key": "val"}
        res = ensure_text(data)
        parsed = json.loads(res)
        self.assertEqual(parsed, data)

    def test_ensure_text_document(self):
        doc = MockDocument("document content", {"file_name": "test.pdf"})
        self.assertEqual(ensure_text(doc), "document content")

    def test_ensure_text_complex_mixed(self):
        doc = MockDocument("doc inside list")
        mixed = [
            "start",
            {"info": "dict in list"},
            [doc, None, "end"]
        ]
        res = ensure_text(mixed)
        self.assertIn("start", res)
        self.assertIn("dict in list", res)
        self.assertIn("doc inside list", res)
        self.assertIn("end", res)

if __name__ == "__main__":
    unittest.main()
