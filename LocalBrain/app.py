from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault(
    "STREAMLIT_HOME", str(Path(__file__).resolve().parent / ".streamlit_home")
)

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

st.set_page_config(page_title="LocalBrain", page_icon="🧠", layout="wide")

def main() -> None:
    pages_dir = Path(__file__).resolve().parent / "pages"
    chat_page = st.Page(str(pages_dir / "chat.py"), title="💬 对话", icon="💬")
    kb_page = st.Page(str(pages_dir / "knowledge_base.py"), title="📚 知识库", icon="📚")
    models_page = st.Page(str(pages_dir / "models.py"), title="⚙️ 模型管理", icon="⚙️")

    nav = st.navigation([chat_page, kb_page, models_page])
    nav.run()


if __name__ == "__main__":
    main()
