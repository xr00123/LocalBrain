from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from nicegui import ui


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str


NAV: List[NavItem] = [
    NavItem(key="chat", label="新对话", icon="edit_square"),
    NavItem(key="kb", label="知识库", icon="folder"),
    NavItem(key="models", label="模型管理", icon="memory"),
]

_tailwind_injected = False


def inject_tailwind() -> None:
    global _tailwind_injected
    if _tailwind_injected:
        return
    ui.add_head_html(
        """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html, body { 
    height: 100%; 
    margin: 0; 
    padding: 0; 
    overflow: hidden; 
    background: #FFFFFF; 
    font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, -apple-system, sans-serif; 
  }
  code, pre, kbd, samp {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  }
  .no-scrollbar { scrollbar-width: none !important; -ms-overflow-style: none !important; }
  .no-scrollbar::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
  #chat-scroll { scrollbar-width: none !important; -ms-overflow-style: none !important; }
  #chat-scroll::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
</style>
"""
    )
    _tailwind_injected = True


def create_layout(on_nav: Callable[[str], None], init_tab: str = "chat") -> Tuple[ui.element, Callable[[str], None]]:
    inject_tailwind()

    nav_items: Dict[str, ui.element] = {}
    base_cls = "relative z-10 w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all cursor-pointer"
    active_text_cls = "text-indigo-400 font-bold"
    inactive_text_cls = "text-slate-200 hover:text-white"
    
    # Initial position calculation
    init_idx = next((i for i, item in enumerate(NAV) if item.key == init_tab), 0)
    # Top padding (24px) + Index * (Height 40px + Gap 8px)
    init_top = 24 + init_idx * 48

    with ui.element("div").classes("flex h-screen w-full bg-white"):
        with ui.element("aside").classes(
            "fixed inset-y-0 left-0 w-[260px] bg-slate-900 text-slate-200 border-r border-slate-800 z-50 flex flex-col"
        ):
            # Logo Area - Click to go to chat
            with ui.element("div").classes(
                "h-16 flex items-center px-6 gap-3 border-b border-slate-800/60 hover:bg-white/5 transition-colors cursor-pointer"
            ).on("click", lambda: on_nav("chat")):
                with ui.element("div").classes(
                    "w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20"
                ):
                    ui.icon("psychology", size="20px").classes("text-white")
                ui.label("LocalBrain").classes("text-base font-semibold text-white tracking-tight")

            # Nav Menu Container
            with ui.column().classes("flex-1 overflow-y-auto py-6 px-4 gap-2 relative"):
                # Floating Indicator (The "White Box")
                indicator = ui.element("div").classes(
                    "absolute left-4 right-4 h-10 bg-white/10 border border-white/20 rounded-lg transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                ).style(f"top: {init_top}px")

                for item in NAV:
                    # Navigation Item
                    with ui.element("div").classes(base_cls).on(
                        "click", lambda _, k=item.key: on_nav(k)
                    ) as el:
                        ui.icon(item.icon).classes("text-sm transition-colors")
                        ui.label(item.label).classes("text-sm transition-colors truncate")
                        nav_items[item.key] = el
        
        def update_sidebar(active_key: str):
            # Update Indicator Position
            try:
                idx = next(i for i, item in enumerate(NAV) if item.key == active_key)
                new_top = 24 + idx * 48
                indicator.style(f"top: {new_top}px")
            except StopIteration:
                pass # active_key not in NAV (e.g. unknown route)

            # Update Text Colors
            for key, el in nav_items.items():
                is_active = key == active_key
                el.classes(remove=f"{active_text_cls} {inactive_text_cls}")
                el.classes(add=active_text_cls if is_active else inactive_text_cls)

        # Init sidebar state
        update_sidebar(init_tab)

        # Main Content Area
        main_cls = "ml-[260px] flex-1 flex flex-col h-full bg-white relative overflow-hidden"
        main_container = ui.element("main").classes(main_cls)
        
        return main_container, update_sidebar
