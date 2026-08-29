"""Small embedding-based RAG index for the synthetic business knowledge base."""

import math
from collections.abc import Callable
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel


EMBEDDING_MODEL = "text-embedding-3-small"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "knowledge_index.json"
EmbeddingFunction = Callable[[list[str]], list[list[float]]]


class KnowledgeChunk(BaseModel):
    """One retrievable document section."""

    id: str
    source: str
    document_title: str
    section_title: str
    content: str


class IndexedKnowledgeChunk(KnowledgeChunk):
    """A document chunk paired with its vector representation."""

    embedding: list[float]


class KnowledgeIndex(BaseModel):
    """Local vector index metadata and embedded chunks."""

    embedding_model: str
    chunks: list[IndexedKnowledgeChunk]


class KnowledgeHit(BaseModel):
    """One user-visible retrieval result with a source citation."""

    source: str
    document_title: str
    section_title: str
    content: str
    score: float
    citation: str


def load_knowledge_chunks(directory: str | Path) -> list[KnowledgeChunk]:
    """Split Markdown files by level-two headings into retrievable chunks."""
    knowledge_directory = Path(directory)
    if not knowledge_directory.exists():
        raise FileNotFoundError(f"找不到知识库目录：{knowledge_directory}")

    chunks: list[KnowledgeChunk] = []
    for path in sorted(knowledge_directory.glob("*.md")):
        document_title = path.stem
        section_title = "简介"
        buffer: list[str] = []
        section_index = 0

        def flush() -> None:
            nonlocal buffer, section_index
            content = "\n".join(buffer).strip()
            if not content:
                buffer = []
                return
            section_index += 1
            chunks.append(
                KnowledgeChunk(
                    id=f"{path.stem}-{section_index}",
                    source=path.name,
                    document_title=document_title,
                    section_title=section_title,
                    content=content,
                )
            )
            buffer = []

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                document_title = line[2:].strip()
            elif line.startswith("## "):
                flush()
                section_title = line[3:].strip()
            elif line:
                buffer.append(line)
        flush()

    if not chunks:
        raise ValueError("知识库中没有可索引的 Markdown 内容。")
    return chunks


def create_openai_embeddings(texts: list[str]) -> list[list[float]]:
    """Create vectors in one batch using the configured OpenAI embedding model."""
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Embedding 输入不能为空。")
    response = OpenAI().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def build_knowledge_index(
    knowledge_directory: str | Path = DEFAULT_KNOWLEDGE_DIRECTORY,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    embedder: EmbeddingFunction | None = None,
) -> KnowledgeIndex:
    """Embed all knowledge chunks and save a local JSON vector index."""
    chunks = load_knowledge_chunks(knowledge_directory)
    embedding_function = embedder or create_openai_embeddings
    vectors = embedding_function(
        [
            f"{chunk.document_title}\n{chunk.section_title}\n{chunk.content}"
            for chunk in chunks
        ]
    )
    if len(vectors) != len(chunks):
        raise ValueError("Embedding 数量与知识块数量不一致。")

    index = KnowledgeIndex(
        embedding_model=EMBEDDING_MODEL,
        chunks=[
            IndexedKnowledgeChunk(**chunk.model_dump(), embedding=vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )
    output_path = Path(index_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(index.model_dump_json(), encoding="utf-8")
    return index


def load_knowledge_index(
    index_path: str | Path = DEFAULT_INDEX_PATH,
) -> KnowledgeIndex:
    """Load the prebuilt local vector index."""
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(
            f"找不到知识库索引：{path}。请先运行 scripts/build_knowledge_index.py。"
        )
    return KnowledgeIndex.model_validate_json(path.read_text(encoding="utf-8"))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Calculate cosine similarity without adding a numerical dependency."""
    if len(left) != len(right) or not left:
        raise ValueError("向量维度不一致或为空。")
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot_product / (left_norm * right_norm)


def search_knowledge(
    query: str,
    *,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    top_k: int = 4,
    embedder: EmbeddingFunction | None = None,
) -> list[KnowledgeHit]:
    """Embed a query, rank local chunks, and return source-carrying results."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("知识库检索问题不能为空。")
    if not 1 <= top_k <= 10:
        raise ValueError("top_k 必须在 1 到 10 之间。")

    index = load_knowledge_index(index_path)
    embedding_function = embedder or create_openai_embeddings
    query_vectors = embedding_function([clean_query])
    if len(query_vectors) != 1:
        raise ValueError("查询 Embedding 返回数量异常。")
    query_vector = query_vectors[0]

    ranked = sorted(
        (
            (cosine_similarity(query_vector, chunk.embedding), chunk)
            for chunk in index.chunks
        ),
        key=lambda item: item[0],
        reverse=True,
    )[:top_k]
    return [
        KnowledgeHit(
            source=chunk.source,
            document_title=chunk.document_title,
            section_title=chunk.section_title,
            content=chunk.content,
            score=round(score, 4),
            citation=f"[{chunk.source}#{chunk.section_title}]",
        )
        for score, chunk in ranked
    ]


def retrieve_business_knowledge(query: str, top_k: int = 4) -> list[KnowledgeHit]:
    """Search the project's default synthetic business knowledge base."""
    return search_knowledge(query, top_k=top_k)
