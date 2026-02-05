from __future__ import annotations

import streamlit as st

from LocalBrain.config import SETTINGS
from LocalBrain.core.kb_manager import KBManager


def _fmt_bytes(n: int) -> str:
    if not isinstance(n, int) or n <= 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024.0 or u == units[-1]:
            return f"{f:.0f}{u}" if u == "B" else f"{f:.1f}{u}"
        f /= 1024.0
    return f"{n}B"


st.title("📚 知识库")
metrics_area = st.empty()

kbm = KBManager()
try:
    collections = kbm.list_collections()
except Exception:
    collections = []
if "kb_selected" not in st.session_state:
    st.session_state.kb_selected = collections[0] if collections else ""
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

with st.sidebar:
    if st.button("新建知识库", use_container_width=True):
        dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

        if dialog:

            @dialog("新建知识库")
            def _create_dialog():
                name = st.text_input("知识库名称").strip()
                if st.button("创建", use_container_width=True, disabled=not name):
                    try:
                        kbm.create_collection(name)
                        st.session_state.kb_selected = name
                        st.session_state.uploader_key += 1
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            _create_dialog()

    collections = kbm.list_collections()
    if collections:
        selected_kb = st.sidebar.radio(
            "选择知识库",
            options=collections,
            index=collections.index(st.session_state.kb_selected)
            if st.session_state.kb_selected in collections
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.kb_selected = selected_kb
    else:
        st.info("暂无知识库，请先创建。")

if not st.session_state.kb_selected:
    st.stop()

kb_name = st.session_state.kb_selected
st.subheader(f"当前知识库：{kb_name}")
tab_data, tab_hit, tab_settings = st.tabs(["数据管理", "命中测试", "设置"])

with tab_data:
    notice = st.session_state.pop("kb_notice", None) if hasattr(st.session_state, "pop") else None
    notice_level = (
        st.session_state.pop("kb_notice_level", None) if hasattr(st.session_state, "pop") else None
    )
    if notice:
        if notice_level == "warning":
            st.warning(str(notice))
        else:
            st.success(str(notice))

    with st.expander("🛠️ 解析参数设置 (Advanced Parsing)", expanded=False):
        chunk_size = int(
            st.slider(
                "Chunk Size",
                min_value=100,
                max_value=2000,
                value=500,
                step=50,
                key="kb_chunk_size",
            )
        )
        chunk_overlap = int(
            st.slider(
                "Chunk Overlap",
                min_value=0,
                max_value=500,
                value=50,
                step=10,
                key="kb_chunk_overlap",
            )
        )

    uploaded_files = st.file_uploader(
        "上传 PDF/TXT 文件（可多选）",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key=f"kb_uploader_{st.session_state.uploader_key}",
    )
    if st.button("写入知识库", use_container_width=True, disabled=not uploaded_files):
        with st.spinner("正在解析、切块并写入向量库..."):
            stats = kbm.ingest(
                uploaded_files,
                collection_name=kb_name,
                embedding_model=SETTINGS.embedding_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        files_received = int(stats.get("files_received") or 0)
        files_with_text = int(stats.get("files_with_text") or 0)
        documents_loaded = int(stats.get("documents_loaded") or 0)
        chunks_created = int(stats.get("chunks_created") or 0)
        if files_received > 0 and documents_loaded == 0 and chunks_created == 0:
            st.session_state.kb_notice_level = "warning"
            st.session_state.kb_notice = (
                f"导入完成：选中文件 {files_received} 个，但未提取到可索引文本。"
                "可能是扫描件/图片型 PDF，建议先 OCR 或转换为可复制文本的 PDF/TXT。"
            )
        else:
            st.session_state.kb_notice_level = "success"
            st.session_state.kb_notice = (
                f"导入完成：选中文件 {files_received} 个，成功解析 {files_with_text} 个；"
                f"文档 {documents_loaded} 篇，切片 {chunks_created} 条。"
            )
        st.session_state.uploader_key += 1
        st.rerun()

    try:
        chunk_rows = kbm.list_chunks(kb_name)
    except Exception as e:
        st.error(f"读取知识库失败：{e}")
        chunk_rows = []

    if chunk_rows:
        st.markdown("**文件管理**")
        file_stats = kbm.doc_stats(chunk_rows)
        h1, h2, h3 = st.columns([6, 2, 1])
        h1.markdown("**文件名**")
        h2.markdown("**切片数**")
        h3.markdown("**操作**")
        for row in file_stats:
            filename = str(row.get("文件名", "")).strip()
            chunks = row.get("切片数量", 0)
            if not filename:
                continue
            c1, c2, c3 = st.columns([6, 2, 1])
            c1.write(filename)
            c2.write(int(chunks) if isinstance(chunks, int) else chunks)
            if c3.button("🗑️", key=f"del::{kb_name}::{filename}", type="primary"):
                try:
                    kbm.delete_file(kb_name, filename)
                    msg = f"已删除文件：{filename}"
                    toast = getattr(st, "toast", None)
                    if toast:
                        toast(msg)
                    st.session_state.kb_notice_level = "success"
                    st.session_state.kb_notice = msg
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        st.markdown("**切片预览**")
        sources = sorted({r.source for r in chunk_rows})
        q = st.text_input("🔍 搜索切片内容...", placeholder="输入关键词过滤...", key="kb_chunk_query")
        src_filters = st.multiselect("按文件筛选", options=sources, key="kb_chunk_sources")
        show_rows = chunk_rows
        if src_filters:
            allowed = set(src_filters)
            show_rows = [r for r in show_rows if r.source in allowed]
        if q.strip():
            needle = q.strip().lower()
            show_rows = [r for r in show_rows if needle in (r.content or "").lower()]
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
                    "内容": (r.get("content") or "")
                    if len(r.get("content") or "") <= 400
                    else (r.get("content") or "")[:400] + "…",
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

try:
    file_count, chunk_count = kbm.get_metrics(kb_name)
except Exception:
    file_count, chunk_count = 0, 0
storage_bytes = kbm.get_storage_bytes()
with metrics_area.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("文档总数 (Total Files)", int(file_count))
    c2.metric("切片总数 (Total Chunks)", int(chunk_count))
    c3.metric("存储占用 (Storage)", _fmt_bytes(int(storage_bytes)))
    c4.metric("Embedding 模型", SETTINGS.embedding_model)
