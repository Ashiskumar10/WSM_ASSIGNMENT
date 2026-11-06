"""Unit tests for the Findly WSM text search engine."""

from __future__ import annotations

import unittest

from backend.document_loader import Document, split_paragraphs
from backend.search_engine import SearchEngine
from backend.soundex import soundex
from backend.wildcard_processor import KGramIndex


class SearchEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SearchEngine()
        self.engine.build([
            Document(
                doc_id="doc1::p001",
                title="Information retrieval",
                text="Information retrieval uses an inverted index. The quick brown fox jumps over the lazy dog.",
                source="doc1.txt",
                paragraph_number=1,
            ),
            Document(
                doc_id="doc2::p001",
                title="Search ranking",
                text="A search engine ranks documents with TF-IDF and term frequency. Searching documents is useful.",
                source="doc2.txt",
                paragraph_number=1,
            ),
            Document(
                doc_id="doc3::p001",
                title="Animals",
                text="The cat sleeps near the dog. The dog runs quickly.",
                source="doc3.txt",
                paragraph_number=1,
            ),
            Document(
                doc_id="doc4::p001",
                title="Phrase position",
                text="The state of the art retrieval system stores token positions.",
                source="doc4.txt",
                paragraph_number=1,
            ),
            Document(
                doc_id="doc5::p001",
                title="Names and phonetics",
                text="Rupert is a common example used in phonetic matching.",
                source="doc5.txt",
                paragraph_number=1,
            ),
        ])

    def test_document_count_and_stop_word_removal(self) -> None:
        self.assertEqual(self.engine.index.document_count, 5)
        self.assertNotIn("the", self.engine.index.vocabulary)
        self.assertIn("the", self.engine.index.all_vocabulary)

    def test_phrase_search_uses_positions_and_keeps_stop_words(self) -> None:
        response = self.engine.search('"state of the art"')
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["results"][0]["doc_id"], "doc4::p001")

    def test_boolean_and_or_not_and_parentheses(self) -> None:
        and_result = self.engine.search("cat AND dog", mode="boolean")
        self.assertEqual(and_result["total"], 1)
        self.assertEqual(and_result["results"][0]["doc_id"], "doc3::p001")

        or_result = self.engine.search("cat OR retrieval", mode="boolean")
        self.assertEqual(or_result["total"], 3)

        not_result = self.engine.search("dog AND NOT cat", mode="boolean")
        self.assertEqual(not_result["total"], 1)

        grouped = self.engine.search("(cat OR retrieval) AND dog", mode="boolean")
        self.assertEqual(grouped["total"], 2)
        self.assertEqual({item["doc_id"] for item in grouped["results"]}, {"doc1::p001", "doc3::p001"})

    def test_wildcard_uses_kgram_index(self) -> None:
        self.assertIn("retriev", self.engine.index.kgram_index.expand("retriev*"))
        response = self.engine.search("retriev*")
        self.assertGreaterEqual(response["total"], 2)

    def test_stemming_matches_inflected_forms(self) -> None:
        response = self.engine.search("searching")
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["results"][0]["doc_id"], "doc2::p001")

    def test_ranked_results_include_scores_and_safe_highlighting(self) -> None:
        response = self.engine.search("search engine documents")
        self.assertGreaterEqual(response["total"], 1)
        self.assertTrue(all("score" in item for item in response["results"]))
        self.assertTrue(any("<mark>" in item["snippet_html"] for item in response["results"]))
        self.assertNotIn("<script>", response["results"][0]["snippet_html"])

    def test_soundex_known_pair(self) -> None:
        self.assertEqual(soundex("Smith"), soundex("Smyth"))
        self.assertEqual(soundex("Robert"), soundex("Rupert"))
        self.assertEqual(soundex("Ashcraft"), "A261")

    def test_phonetic_search_expands_soundex_terms(self) -> None:
        exact = self.engine.search("Robert", phonetic=False)
        phonetic = self.engine.search("Robert", phonetic=True)
        self.assertEqual(exact["total"], 0)
        self.assertEqual(phonetic["total"], 1)
        self.assertEqual(phonetic["results"][0]["doc_id"], "doc5::p001")

    def test_automatic_spelling_correction(self) -> None:
        response = self.engine.search("inverted indx")
        self.assertEqual(response["corrected_query"], "inverted index")
        self.assertEqual(response["suggestions"][0]["suggestion"], "index")


    def test_wildcard_mode_uses_kgram_expansion(self) -> None:
        response = self.engine.search("retriev*", mode="wildcard")
        self.assertEqual(response["mode"], "wildcard")
        self.assertGreaterEqual(response["total"], 2)

    def test_spell_correction_can_be_toggled_off(self) -> None:
        enabled = self.engine.search("inverted indx", spell_correct=True)
        disabled = self.engine.search("inverted indx", spell_correct=False)
        self.assertEqual(enabled["corrected_query"], "inverted index")
        self.assertIsNone(disabled["corrected_query"])
        self.assertEqual(disabled["suggestions"], [])

    def test_kgram_question_mark(self) -> None:
        index = KGramIndex(3)
        index.build(["cat", "car", "cart", "dog"])
        self.assertEqual(index.expand("ca?"), ["car", "cat"])

    def test_paragraph_splitting(self) -> None:
        self.assertEqual(split_paragraphs("one\n\n two\n\n\nthree"), ["one", "two", "three"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
