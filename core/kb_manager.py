from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from chromadb import PersistentClient

from config import SETTINGS
from core.processor import get_vectorstore, ingest_files


@dataclass(frozen=True)
class ChunkRow:
    source: str
    page: str
    chunk_index: str
    content: str


class KBManager:
    def __init__(self, persist_dir=None) -> None:
        self._persist_dir = persist_dir or SETTINGS.chroma_persist_dir

    def _client(self) -> PersistentClient:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        return PersistentClient(path=str(self._persist_dir))

    def get_storage_bytes(self) -> int:
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return 0
        total = 0
        for p in self._persist_dir.rglob("*"):
            try:
                if p.is_file():
                    total += int(p.stat().st_size)
            except Exception:
                continue
        return total

    def list_collections(self) -> List[str]:
        cols = self._client().list_collections()
        names: List[str] = []
        for c in cols or []:
            name = getattr(c, "name", None)
            if name:
                names.append(str(name))
        return sorted(set(names))

    def create_collection(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("知识库名称不能为空。")
        if name in set(self.list_collections()):
            raise ValueError("该知识库已存在。")
        self._client().create_collection(name=name)

    def delete_collection(self, name: str) -> None:
        self._client().delete_collection(name=name)

    def clear_collection(self, name: str) -> None:
        client = self._client()
        client.delete_collection(name=name)
        client.create_collection(name=name)

    def delete_file(self, collection_name: str, filename: str) -> None:
        filename = filename.strip()
        if not filename:
            raise ValueError("文件名不能为空。")
        col = self._client().get_collection(name=collection_name)
        col.delete(where={"source": filename})

    def get_metrics(self, collection_name: str) -> Tuple[int, int]:
        col = self._client().get_collection(name=collection_name)
        chunk_count = int(col.count() or 0)
        if chunk_count <= 0:
            return 0, 0
        file_count = 0
        try:
            got = col.get(include=["metadatas"])
            metas = got.get("metadatas") or []
            sources = set()
            for m in metas:
                meta = m or {}
                src = meta.get("source")
                if src:
                    sources.add(str(src))
            file_count = len(sources)
        except Exception:
            file_count = 0
        return file_count, chunk_count

    def ingest(
        self,
        uploaded_files: Iterable,
        collection_name: str,
        embedding_model: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> Dict[str, int]:
        stats = ingest_files(
            uploaded_files,
            collection_name=collection_name,
            reset=False,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return {
            "files_received": stats.files_received,
            "files_with_text": stats.files_with_text,
            "documents_loaded": stats.documents_loaded,
            "chunks_created": stats.chunks_created,
        }

    def list_chunks(self, collection_name: str) -> List[ChunkRow]:
        col = self._client().get_collection(name=collection_name)
        got = col.get(include=["metadatas", "documents"])
        metas = got.get("metadatas") or []
        docs = got.get("documents") or []

        rows: List[ChunkRow] = []
        for i in range(min(len(metas), len(docs))):
            meta = metas[i] or {}
            rows.append(
                ChunkRow(
                    source=str(meta.get("source", "未知来源")),
                    page=str(meta.get("page", "")),
                    chunk_index=str(meta.get("chunk_index", "")),
                    content=str(docs[i] or ""),
                )
            )
        return rows

    def doc_stats(self, rows: List[ChunkRow]) -> List[Dict[str, int]]:
        counter: Dict[str, int] = {}
        for r in rows:
            counter[r.source] = counter.get(r.source, 0) + 1
        return [{"文件名": k, "切片数量": v} for k, v in sorted(counter.items(), key=lambda x: x[0])]

    def hit_test(
        self,
        collection_name: str,
        question: str,
        k: int,
        embedding_model: str,
    ) -> List[Dict]:
        vs = get_vectorstore(collection_name=collection_name, embedding_model=embedding_model)
        try:
            pairs = vs.similarity_search_with_score(question, k=k)
        except Exception:
            pairs = [(d, None) for d in vs.similarity_search(question, k=k)]

        results: List[Dict] = []
        for d, score in pairs:
            meta = d.metadata or {}
            distance = None
            similarity = None
            if isinstance(score, (int, float)):
                distance = float(score)
                similarity = 1.0 / (1.0 + distance)
            text = d.page_content or ""
            results.append(
                {
                    "source": meta.get("source", "未知来源"),
                    "page": meta.get("page", ""),
                    "chunk_index": meta.get("chunk_index", ""),
                    "distance": distance,
                    "similarity": similarity,
                    "content": text,
                }
            )
        return results
