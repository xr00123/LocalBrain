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
        """
        Returns a list of collection IDs (actual ChromaDB names).
        Kept for backward compatibility.
        """
        cols = self._client().list_collections()
        names: List[str] = []
        for c in cols or []:
            name = getattr(c, "name", None)
            if name:
                names.append(str(name))
        return sorted(set(names))

    def list_kb_info(self) -> List[Dict[str, str]]:
        """
        Returns a list of dicts: {'id': 'kb_id', 'name': 'Display Name'}
        """
        cols = self._client().list_collections()
        result = []
        for c in cols or []:
            cid = getattr(c, "name", "")
            if not cid:
                continue
            meta = c.metadata or {}
            display_name = meta.get("display_name", cid)
            result.append({"id": cid, "name": display_name})
        # Sort by display name
        return sorted(result, key=lambda x: x["name"])

    def _validate_display_name(self, name: str) -> None:
        if not name:
            raise ValueError("知识库名称不能为空。")
        # Check for duplicate display name
        current_list = self.list_kb_info()
        if any(kb["name"] == name for kb in current_list):
            raise ValueError(f"知识库 '{name}' 已存在。")

    def create_collection(self, name: str) -> None:
        import uuid
        name = name.strip()
        self._validate_display_name(name)
        
        # Generate a safe internal ID
        # Using uuid4 to ensure uniqueness and compliance with ChromaDB naming rules
        safe_id = f"kb_{uuid.uuid4().hex}"
        
        self._client().create_collection(name=safe_id, metadata={"display_name": name})

    def delete_collection(self, name: str) -> None:
        # name here is the ID
        self._client().delete_collection(name=name)

    def rename_collection(self, kb_id: str, new_name: str) -> None:
        """
        Renames the display name of a knowledge base.
        kb_id: The internal ID of the collection.
        new_name: The new display name.
        """
        kb_id = kb_id.strip()
        new_name = new_name.strip()
        
        # Check if new name is valid and doesn't exist (excluding self)
        if not new_name:
            raise ValueError("新名称不能为空。")
            
        current_list = self.list_kb_info()
        # Check duplicates
        for kb in current_list:
            if kb["name"] == new_name and kb["id"] != kb_id:
                raise ValueError(f"知识库 '{new_name}' 已存在。")
        
        try:
            col = self._client().get_collection(name=kb_id)
            # Only update metadata, not the underlying collection name
            col.modify(metadata={"display_name": new_name})
        except Exception as e:
            raise ValueError(f"重命名失败: {str(e)}")

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
