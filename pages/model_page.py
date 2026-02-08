from __future__ import annotations

import time
import streamlit as st

from core.model_manager import ModelManager


def app():
    st.title("⚙️ 模型管理")

    mgr = ModelManager()
    ok, err = mgr.check_connection()
    if not ok:
        st.error(f"Ollama 未启动或不可用：{err}\n\n请先启动 Ollama（默认端口 11434）。")

    if "delete_target" not in st.session_state:
        st.session_state.delete_target = None

    st.subheader("本地模型列表")
    models = []
    if ok:
        try:
            models = mgr.list_models()
        except Exception as e:
            st.error(f"获取模型列表失败：{e}")

    if models:
        if st.session_state.delete_target:
            target = st.session_state.delete_target

            @st.dialog("确认删除")
            def _confirm_delete():
                st.warning(f"确定要删除模型 `{target}` 吗？该操作不可恢复。")
                c1, c2 = st.columns(2)
                if c1.button("确认删除", type="primary", use_container_width=True, disabled=not ok):
                    ok_del, msg = mgr.delete_model(target)
                    if ok_del:
                        st.session_state.delete_target = None
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                if c2.button("取消", use_container_width=True):
                    st.session_state.delete_target = None
                    st.rerun()

            _confirm_delete()

        with st.container(border=True):
            h1, h2, h3, h4, h5 = st.columns([3.2, 1.6, 1.6, 1.6, 1.4])
            h1.markdown("**模型名**")
            h2.markdown("**大小**")
            h3.markdown("**家族**")
            h4.markdown("**参数量**")
            h5.markdown("**操作**")

            for m in models:
                c1, c2, c3, c4, c5 = st.columns([3.2, 1.6, 1.6, 1.6, 1.4])
                c1.write(m["name"])
                c2.write(m["size"])
                c3.write(m["family"])
                c4.write(m["params"])
                if c5.button("🗑️ 删除", key=f"delete_model__{m['name']}", use_container_width=True, disabled=not ok):
                    st.session_state.delete_target = m["name"]
                    st.rerun()
    else:
        st.info("暂无本地模型。")

    st.divider()
    st.subheader("下载专区")

    dl_status = mgr.get_download_status()
    current_status = dl_status.get("status")

    if current_status == "running":
        m_name = dl_status.get("model_name") or "未知模型"
        percent = dl_status.get("percent", 0.0)
        msg = dl_status.get("message", "")
        
        st.info(f"正在后台下载模型: **{m_name}**", icon="⏳")
        st.progress(percent)
        st.caption(msg)
        
        time.sleep(1)
        st.rerun()

    elif current_status == "success":
        m_name = dl_status.get("model_name")
        st.success(f"模型 **{m_name}** 下载成功！", icon="✅")
        if st.button("完成", type="primary", use_container_width=True):
            mgr.clear_download_status()
            st.rerun()

    elif current_status == "error":
        m_name = dl_status.get("model_name")
        err_msg = dl_status.get("message")
        st.error(f"模型 **{m_name}** 下载失败: {err_msg}", icon="❌")
        if st.button("清除状态", use_container_width=True):
            mgr.clear_download_status()
            st.rerun()

    else:
        model_name = st.text_input(
            "输入模型名称",
            placeholder="例如: deepseek-r1:7b, llama3.1, qwen2.5:7b",
        ).strip()

        if not ok:
            st.caption("Ollama 不可用，无法下载模型。请先启动 Ollama（默认端口 11434）。")

        start = st.button("立即下载", use_container_width=True, disabled=not ok or not model_name)
        if start and model_name:
            ok_start, start_msg = mgr.start_pull_model_thread(model_name)
            if ok_start:
                if hasattr(st, "toast"):
                    st.toast("已开始下载，可切换页面/刷新后继续查看进度。", icon="⬇️")
                st.rerun()
            else:
                st.error(start_msg)


if __name__ == "__main__":
    app()
