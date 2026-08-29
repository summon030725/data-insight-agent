"""Offline tests for Markdown chunking and vector retrieval."""

import tempfile
import unittest
from pathlib import Path

from data_agent import (
    build_knowledge_index,
    load_knowledge_chunks,
    search_knowledge,
)
from data_agent.rag import cosine_similarity


def fake_embedder(texts: list[str]) -> list[list[float]]:
    """Create tiny deterministic vectors for tests without API calls."""
    return [
        [
            float(text.casefold().count("退款")),
            float(text.casefold().count("渠道")),
            float(text.casefold().count("monitor")),
            1.0,
        ]
        for text in texts
    ]


class RagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.knowledge_directory = cls.project_root / "knowledge"

    def test_markdown_documents_are_split_by_section(self) -> None:
        chunks = load_knowledge_chunks(self.knowledge_directory)

        self.assertEqual(len({chunk.source for chunk in chunks}), 4)
        self.assertGreaterEqual(len(chunks), 15)
        self.assertTrue(all(chunk.section_title for chunk in chunks))

    def test_cosine_similarity_ranks_identical_vectors_highest(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1, 2], [1, 2]), 1.0)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_search_returns_source_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / "knowledge_index.json"
            build_knowledge_index(
                self.knowledge_directory,
                index_path,
                embedder=fake_embedder,
            )

            hits = search_knowledge(
                "Monitor 高额退款如何处理？",
                index_path=index_path,
                top_k=3,
                embedder=fake_embedder,
            )

        self.assertEqual(len(hits), 3)
        self.assertIn("product_service_guide.md", hits[0].source)
        self.assertIn("#", hits[0].citation)


if __name__ == "__main__":
    unittest.main()
