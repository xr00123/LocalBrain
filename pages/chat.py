from __future__ import annotations

import streamlit as st

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from LocalBrain.config import SETTINGS
from LocalBrain.core.kb_manager import KBManager
from LocalBrain.core.model_manager import ModelManager
from LocalBrain.core.processor import get_vectorstore


st.title("💬 对话")


def _build_llm(model: str, temperature: float, max_tokens: int) -> ChatOllama:
    kwargs = {"model": model, "temperature": temperature}
    if max_tokens:
        kwargs["num_predict"] = int(max_tokens)
    try:
        return ChatOllama(**kwargs)
    except TypeError:
        return ChatOllama(model=model)


def _to_lc_messages(history: list[dict]) -> list:
    msgs = [SystemMessage(content="你是一个离线本地助手，回答要简洁准确。")]
    for m in history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    return msgs


mgr = ModelManager()
kbm = KBManager()
try:
    model_names = [m["name"] for m in mgr.list_models()] or [SETTINGS.llm_model]
except Exception:
    model_names = [SETTINGS.llm_model]

try:
    collections = kbm.list_collections()
except Exception:
    collections = []
collection_options = ["（不使用知识库）", *collections]

with st.sidebar:
    st.subheader("对话设置")
    model_name = st.selectbox("模型选择", options=model_names, index=0)
    kb_choice = st.selectbox(
        "知识库关联", options=collection_options, index=0, help="选择（不使用知识库）则纯聊。"
    )
    temperature = st.slider("温度", min_value=0.0, max_value=1.5, value=0.2, step=0.05)
    max_tokens = int(st.number_input("最大输出 Token 数", min_value=0, max_value=32768, value=2048, step=128))
    if st.button("清空对话", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("请输入你的问题…")
if question:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("正在生成回复..."):
            llm = _build_llm(model_name, temperature=temperature, max_tokens=max_tokens)
            history = _to_lc_messages(st.session_state.chat_messages)
            answer = ""
            sources_md = ""

            if kb_choice != "（不使用知识库）":
                vs = get_vectorstore(collection_name=kb_choice, embedding_model=SETTINGS.embedding_model)
                docs = vs.similarity_search(question, k=SETTINGS.retrieval_k)
                context = "\n\n".join(
                    [
                        f"[{i+1}] {d.metadata.get('source','未知来源')}"
                        + (f"（第 {d.metadata.get('page')} 页）" if d.metadata.get("page") else "")
                        + f"\n{d.page_content}"
                        for i, d in enumerate(docs)
                    ]
                )
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "你是本地知识库问答助手。只使用给定上下文回答；若上下文不足，直接说不知道。",
                        ),
                        ("human", "问题：{question}\n\n上下文：\n{context}"),
                    ]
                )
                resp = llm.invoke(prompt.format_messages(question=question, context=context))
                answer = getattr(resp, "content", str(resp)).strip()

                if docs:
                    lines = []
                    seen = set()
                    for d in docs:
                        meta = d.metadata or {}
                        key = (meta.get("source"), meta.get("page"))
                        if key in seen:
                            continue
                        seen.add(key)
                        if meta.get("page"):
                            lines.append(f"- {meta.get('source','未知来源')}（第 {meta.get('page')} 页）")
                        else:
                            lines.append(f"- {meta.get('source','未知来源')}")
                    sources_md = "\n".join(lines)
            else:
                resp = llm.invoke(history)
                answer = getattr(resp, "content", str(resp)).strip()

            if not answer:
                answer = "没有生成有效回复。"
            st.markdown(answer)
            if sources_md:
                st.markdown("**来源**")
                st.markdown(sources_md)

    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
