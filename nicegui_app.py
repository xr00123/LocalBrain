from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from nicegui import app, ui

from LocalBrain.nicegui_ui.chat_page import chat_page_content
from LocalBrain.nicegui_ui.kb_page import kb_page_content
from LocalBrain.nicegui_ui.layout import create_layout
from LocalBrain.nicegui_ui.model_page import model_page_content


def build_page(init_tab: str = "chat") -> None:
    # 响应式状态：当前激活的标签页
    current_tab = init_tab
    container = None
    update_sidebar = None

    def render_content():
        if not container:
            return
        container.clear()
        with container:
            if current_tab == "chat":
                chat_page_content()
            elif current_tab == "kb":
                kb_page_content()
            elif current_tab == "models":
                model_page_content()
            else:
                chat_page_content()

    def on_nav(key: str):
        nonlocal current_tab
        if current_tab == key:
            return
        current_tab = key
        # 更新 URL，不刷新页面
        target_url = f"/{key}" if key != "chat" else "/"
        ui.run_javascript(f"window.history.pushState({{}}, '', '{target_url}');")
        # 更新侧边栏高亮
        if update_sidebar:
            update_sidebar(key)
        # 渲染新内容
        render_content()

    # 创建布局，传入导航回调和当前状态
    container, update_sidebar = create_layout(on_nav, init_tab)
    
    # 渲染初始内容
    render_content()


@ui.page("/")
def _root() -> None:
    build_page("chat")


@ui.page("/chat")
def _chat() -> None:
    build_page("chat")


@ui.page("/chat/new")
def _chat_new() -> None:
    app.storage.user["chat_messages"] = []
    ui.navigate.to("/")


@ui.page("/kb")
def _kb() -> None:
    build_page("kb")


@ui.page("/models")
def _models() -> None:
    build_page("models")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="LocalBrain",
        port=8503,
        storage_secret=os.getenv("LOCALBRAIN_STORAGE_SECRET") or secrets.token_urlsafe(32),
    )
