from __future__ import annotations

import streamlit as st

from LocalBrain.config import SETTINGS
from LocalBrain.core.kb_manager import KBManager


st.title("📚 知识库")

kbm = KBManager()
try:
    collections = kbm.list_collections()
except Exception:
    collections = []
if "kb_selected" not in st.session_state:
    st.session_state.kb_selected = collections[0] if collections else ""

left, right = st.columns([1, 3], gap="large")

with left:
    st.subheader("知识库")
    if st.button("新建知识库", use_container_width=True):
        dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

        if dialog:

            @dialog("新建知识库")
            def _create_dialog():
                name = st.text_input("知识库名称").strip()
                if st.button("创建", use_container_width=True, disabled=not name):
                    try:
                        kbm.create_collection(name)
                        st.success("创建成功。")
                        st.session_state.kb_selected = name
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            _create_dialog()
        else:
            st.session_state._kb_create_open = True

    collections = kbm.list_collections()
    if collections:
        st.session_state.kb_selected = st.selectbox(
            "选择知识库", options=collections, index=collections.index(st.session_state.kb_selected)
            if st.session_state.kb_selected in collections
            else 0
        )
    else:
        st.info("暂无知识库，请先创建。")

with right:
    if not st.session_state.kb_selected:
        st.stop()

    kb_name = st.session_state.kb_selected
    st.subheader(f"当前知识库：{kb_name}")
    tab_data, tab_hit, tab_settings = st.tabs(["数据管理", "命中测试", "设置"])

    with tab_data:
        uploaded_files = st.file_uploader(
            "上传 PDF/TXT 文件（可多选）",
            type=["pdf", "txt"],
            accept_multiple_files=True,
        )
        if st.button("写入知识库", use_container_width=True, disabled=not uploaded_files):
            with st.spinner("正在解析、切块并写入向量库..."):
                stats = kbm.ingest(
                    uploaded_files,
                    collection_name=kb_name,
                    embedding_model=SETTINGS.embedding_model,
                )
            st.success(f"导入完成：文档 {stats['documents_loaded']} 篇，切片 {stats['chunks_created']} 条。")

        try:
            chunk_rows = kbm.list_chunks(kb_name)
        except Exception as e:
            st.error(f"读取知识库失败：{e}")
            chunk_rows = []

        if chunk_rows:
            st.markdown("**已上传文档**")
            st.dataframe(kbm.doc_stats(chunk_rows), use_container_width=True, hide_index=True)

            st.markdown("**切片预览**")
            sources = sorted({r.source for r in chunk_rows})
            src_filter = st.selectbox("按文件过滤", options=["（全部）", *sources], index=0)
            show_rows = chunk_rows if src_filter == "（全部）" else [r for r in chunk_rows if r.source == src_filter]
            limit = int(st.slider("展示条数", min_value=10, max_value=200, value=50, step=10))
            table_rows = []
            for r in show_rows[:limit]:
                content = r.content or ""
                table_rows.append(
                    {
                        "文件": r.source,
                        "页码": r.page,
                        "切片序号": r.chunk_index,
                        "内容": content if len(content) <= 400 else content[:400] + "…",
                    }
                )
            st.dataframe(table_rows, use_container_width=True, hide_index=True)
        else:
            st.info("当前知识库暂无数据。")

    with tab_hit:
        q = st.text_input("测试问题")
        top_n = int(st.slider("召回条数", min_value=1, max_value=10, value=4, step=1))
        if st.button("开始测试", use_container_width=True, disabled=not q.strip()):
            results = kbm.hit_test(
                collection_name=kb_name,
                question=q,
                k=top_n,
                embedding_model=SETTINGS.embedding_model,
            )
            st.dataframe(
                [
                    {
                        "文件": r.get("source", "未知来源"),
                        "页码": r.get("page", ""),
                        "切片序号": r.get("chunk_index", ""),
                        "距离": r.get("distance"),
                        "相似度": r.get("similarity"),
                        "内容": (r.get("content") or "") if len(r.get("content") or "") <= 400 else (r.get("content") or "")[:400] + "…",
                    }
                    for r in results
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab_settings:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("清空该知识库", use_container_width=True):
                try:
                    kbm.clear_collection(kb_name)
                    st.success("已清空。")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with col2:
            if st.button("删除该知识库", use_container_width=True):
                try:
                    kbm.delete_collection(kb_name)
                    st.success("已删除。")
                    st.session_state.kb_selected = ""
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
