from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from config import SETTINGS


@dataclass(frozen=True)
class RAGResult:
    answer: str
    sources: List[Document]


def _format_context(docs: List[Document]) -> str:
    parts: List[str] = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        src = meta.get("source", "未知来源")
        page = meta.get("page")
        header = f"[{i}] {src}" + (f"（第 {page} 页）" if page else "")
        parts.append(f"{header}\n{d.page_content}")
    return "\n\n".join(parts)


def ask(
    question: str,
    vectorstore,
    llm_model: Optional[str] = None,
    k: Optional[int] = None,
) -> RAGResult:
    retriever = vectorstore.as_retriever(search_kwargs={"k": k or SETTINGS.retrieval_k})
    try:
        docs = retriever.get_relevant_documents(question)
    except Exception:
        docs = retriever.invoke(question)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是本地知识库问答助手。只使用给定的上下文回答；若上下文不足，直接说不知道。",
            ),
            ("human", "问题：{question}\n\n上下文：\n{context}"),
        ]
    )

    llm = ChatOllama(model=llm_model or SETTINGS.llm_model)
    messages = prompt.format_messages(question=question, context=_format_context(docs))
    resp = llm.invoke(messages)
    answer = getattr(resp, "content", str(resp)).strip()
    return RAGResult(answer=answer, sources=docs)
