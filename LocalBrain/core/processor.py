from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

from LocalBrain.config import SETTINGS


@dataclass(frozen=True)
class IngestStats:
    documents_loaded: int
    chunks_created: int


def _ensure_persist_dir() -> Path:
    persist_dir = SETTINGS.chroma_persist_dir
    persist_dir.mkdir(parents=True, exist_ok=True)
    return persist_dir


def load_uploaded_files(uploaded_files: Iterable) -> List[Document]:
    docs: List[Document] = []
    for uf in uploaded_files:
        name = getattr(uf, "name", "uploaded")
        if hasattr(uf, "getvalue"):
            data = uf.getvalue()
        else:
            try:
                uf.seek(0)
            except Exception:
                pass
            data = uf.read()
        suffix = Path(name).suffix.lower()

        if suffix == ".pdf":
            reader = PdfReader(BytesIO(data))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={"source": name, "page": i + 1, "type": "pdf"},
                        )
                    )
        else:
            text = data.decode("utf-8", errors="ignore")
            if text.strip():
                docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": name, "type": "text"},
                    )
                )
    return docs


def split_documents(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=SETTINGS.chunk_size,
        chunk_overlap=SETTINGS.chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    per_source_idx: dict[str, int] = {}
    for ch in chunks:
        meta = ch.metadata or {}
        src = str(meta.get("source") or "未知来源")
        per_source_idx[src] = per_source_idx.get(src, 0) + 1
        meta["chunk_index"] = per_source_idx[src]
        ch.metadata = meta
    return chunks


def get_vectorstore(
    collection_name: Optional[str] = None,
    embedding_model: Optional[str] = None,
) -> Chroma:
    persist_dir = _ensure_persist_dir()
    embeddings = OllamaEmbeddings(model=embedding_model or SETTINGS.embedding_model)
    return Chroma(
        persist_directory=str(persist_dir),
        collection_name=collection_name or SETTINGS.collection_name,
        embedding_function=embeddings,
    )


def reset_vectorstore(
    collection_name: Optional[str] = None,
    embedding_model: Optional[str] = None,
) -> None:
    try:
        vs = get_vectorstore(collection_name=collection_name, embedding_model=embedding_model)
        vs.delete_collection()
    except Exception:
        pass


def ingest_files(
    uploaded_files: Iterable,
    collection_name: Optional[str] = None,
    reset: bool = False,
    embedding_model: Optional[str] = None,
) -> IngestStats:
    if reset:
        reset_vectorstore(collection_name=collection_name, embedding_model=embedding_model)

    docs = load_uploaded_files(uploaded_files)
    chunks = split_documents(docs)
    vs = get_vectorstore(collection_name=collection_name, embedding_model=embedding_model)
    if chunks:
        vs.add_documents(chunks)
        vs.persist()
    return IngestStats(documents_loaded=len(docs), chunks_created=len(chunks))
