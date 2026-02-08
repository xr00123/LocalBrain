from __future__ import annotations

import ctypes
import shutil
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from nicegui import ui

from core.model_manager import ModelManager


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


@dataclass
class _MemoryStatus:
    total: int
    available: int


def _memory_status_windows() -> Optional[_MemoryStatus]:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)) == 0:
        return None
    return _MemoryStatus(total=int(stat.ullTotalPhys), available=int(stat.ullAvailPhys))


def _disk_status(path: str) -> Tuple[int, int, int]:
    usage = shutil.disk_usage(path)
    return int(usage.total), int(usage.used), int(usage.free)


def model_page_content() -> None:
    mgr = ModelManager()

    def _content() -> None:
        ok, err = mgr.check_connection()
        if not ok:
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("Ollama 未启动或不可用").classes("font-bold text-slate-900")
                ui.label(str(err)).classes("text-sm text-gray-500 font-medium mt-1")

        models = []
        if ok:
            try:
                models = mgr.list_models()
            except Exception as ex:
                ui.notify(f"获取模型列表失败：{ex}", type="negative")
                models = []

        mem = _memory_status_windows()
        disk_total, disk_used, disk_free = _disk_status(".")
        model_count = len(models)
        model_total_size = 0
        for m in models:
            size = m.get("size_bytes")
            if isinstance(size, int):
                model_total_size += size

        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-4 gap-6"):
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("模型数量").classes("text-sm text-gray-500 font-medium")
                ui.label(str(model_count)).classes("text-3xl font-bold text-slate-900 mt-2")
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("模型占用").classes("text-sm text-gray-500 font-medium")
                ui.label(_fmt_bytes(int(model_total_size))).classes("text-3xl font-bold text-slate-900 mt-2")
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("磁盘剩余").classes("text-sm text-gray-500 font-medium")
                ui.label(_fmt_bytes(int(disk_free))).classes("text-3xl font-bold text-slate-900 mt-2")
                ui.label(f"总计 {_fmt_bytes(int(disk_total))}").classes("text-sm text-gray-500 font-medium mt-2")
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("可用内存").classes("text-sm text-gray-500 font-medium")
                ui.label(_fmt_bytes(int(mem.available if mem else 0))).classes(
                    "text-3xl font-bold text-slate-900 mt-2"
                )
                if mem:
                    ui.label(f"总计 {_fmt_bytes(int(mem.total))}").classes(
                        "text-sm text-gray-500 font-medium mt-2"
                    )

        ui.separator().classes("my-8")

        with ui.element("div").classes("grid grid-cols-1 lg:grid-cols-3 gap-6"):
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6 lg:col-span-2"):
                ui.label("本地模型").classes("font-bold text-slate-900")
                ui.label("可删除不需要的模型以释放空间。").classes("text-sm text-gray-500 font-medium mt-1")

                if not models:
                    with ui.column().classes("w-full items-center justify-center py-12"):
                        ui.icon("inventory_2").classes("text-6xl text-gray-200 mb-4")
                        ui.label("暂无本地模型").classes("text-lg font-medium text-gray-400")
                        ui.label("请从右侧下载模型").classes("text-sm text-gray-400")
                else:
                    with ui.element("div").classes("w-full overflow-x-auto mt-6"):
                        # Header
                        with ui.row().classes("min-w-[600px] grid grid-cols-12 gap-4 px-4 py-3 bg-gray-50/50 rounded-t-lg border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wider"):
                            ui.label("模型名称").classes("col-span-5")
                            ui.label("大小").classes("col-span-2")
                            ui.label("家族").classes("col-span-2")
                            ui.label("参数").classes("col-span-2")
                            ui.label("操作").classes("col-span-1 text-right")

                        # Rows
                        with ui.column().classes("min-w-[600px] w-full divide-y divide-gray-100"):
                            for m in models:
                                with ui.row().classes("w-full grid grid-cols-12 gap-4 px-4 py-4 hover:bg-gray-50 transition-colors group items-center"):
                                    # Name
                                    with ui.row().classes("col-span-5 items-center gap-3"):
                                        with ui.element("div").classes("p-2 rounded-lg bg-indigo-50 text-indigo-600"):
                                            ui.icon("smart_toy").classes("text-lg")
                                        with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                                            with ui.row().classes("items-center gap-2 w-full"):
                                                ui.label(m["name"]).classes("font-semibold text-slate-700 truncate text-sm flex-1 min-w-0").props(f"title='{m['name']}'")
                                                # Copy button
                                                ui.button(icon="content_copy", on_click=lambda _, x=m["name"]: (ui.run_javascript(f"navigator.clipboard.writeText('{x}')"), ui.notify("已复制模型名称"))).props("flat round dense size=xs").classes("text-gray-300 hover:text-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity flex-none")
                                    
                                    # Size
                                    ui.label(m["size"]).classes("col-span-2 text-sm text-gray-600 font-mono")

                                    # Family
                                    with ui.element("div").classes("col-span-2"):
                                        if m["family"] and m["family"] != "?":
                                            ui.label(m["family"]).classes("text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full inline-block")
                                        else:
                                            ui.label("-").classes("text-gray-400 text-sm")
                                    
                                    # Params
                                    ui.label(m["params"]).classes("col-span-2 text-sm text-gray-600 font-mono")
                                    
                                    # Actions
                                    with ui.element("div").classes("col-span-1 text-right"):
                                        ui.button(icon="delete", on_click=lambda n=m["name"]: _delete_model(n)).props("flat round dense color=red").classes("opacity-60 hover:opacity-100").tooltip("删除模型")

            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6 lg:col-span-1"):
                ui.label("下载专区").classes("font-bold text-slate-900")
                
                @ui.refreshable
                def render_download_panel():
                    dl = mgr.get_download_status()
                    status = dl.get("status")
                    
                    if status == "running":
                        m_name = dl.get("model_name") or "未知模型"
                        ui.label(f"正在后台下载：{m_name}").classes("text-sm text-slate-900 font-medium mt-4")
                        
                        pg = ui.linear_progress(value=float(dl.get("percent") or 0.0)).classes("h-2 rounded-full mt-3")
                        lbl_msg = ui.label(dl.get("message") or "").classes(
                            "text-xs text-gray-500 font-medium mt-2 whitespace-pre-wrap break-all max-h-32 overflow-y-auto"
                        )
                        
                        def _cancel():
                            try:
                                mgr.cancel_download()
                                ui.notify("已发送取消请求", type="warning")
                            except Exception as ex:
                                ui.notify(f"取消失败: {ex}", type="negative")
                            render_download_panel.refresh()

                        ui.button("取消下载", on_click=_cancel).classes(
                            "mt-4 bg-red-50 text-red-600 rounded-lg px-4 py-2 hover:bg-red-100 w-full text-sm font-medium border border-red-200"
                        )
                        
                        def _update_status():
                            new_dl = mgr.get_download_status()
                            if new_dl.get("status") != "running":
                                render_download_panel.refresh()
                            else:
                                pg.value = float(new_dl.get("percent") or 0.0)
                                lbl_msg.set_text(new_dl.get("message") or "")
                        
                        ui.timer(0.5, _update_status)
                        
                    elif status == "success":
                        ui.label(f"下载完成：{dl.get('model_name')}").classes("text-sm text-slate-900 font-medium mt-4")
                        def _done():
                            try:
                                mgr.clear_download_status()
                            except Exception:
                                pass
                            ui.navigate.to("/models")
                        
                        ui.button("完成", on_click=_done).classes("mt-4 bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800 w-full")
                        
                    elif status == "error":
                        ui.label("下载失败").classes("text-sm text-slate-900 font-medium mt-4")
                        ui.label(str(dl.get("message") or "")).classes("text-xs text-gray-500 font-medium mt-2")
                        def _clear():
                            try:
                                mgr.clear_download_status()
                            except Exception:
                                pass
                            render_download_panel.refresh()

                        ui.button("清除状态", on_click=_clear).classes("mt-4 bg-gray-100 text-gray-900 rounded-lg hover:bg-gray-200 px-4 py-2 w-full")
                        
                    else:
                        ui.label("输入模型名称后开始下载。").classes("text-sm text-gray-500 font-medium mt-1")
                        name_in = ui.input(placeholder="例如: deepseek-r1:7b, llama3.1, qwen2.5:7b", label="模型名称").classes("mt-5 w-full rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500")
                        
                        def _start():
                            n = str(name_in.value or "").strip()
                            if not n:
                                ui.notify("请输入模型名称。", type="warning")
                                return
                            if not ok:
                                ui.notify("Ollama 不可用。", type="negative")
                                return
                            success, msg = mgr.start_pull_model_thread(n)
                            ui.notify(msg, type="positive" if success else "negative")
                            render_download_panel.refresh()
                            
                        btn = ui.button("立即下载", on_click=_start).classes("mt-4 bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800 w-full")
                        if not ok:
                            btn.disable()
                            ui.label("Ollama 不可用，无法下载模型。").classes("text-xs text-gray-500 font-medium mt-2")

                render_download_panel()

    def _delete_model(name: str) -> None:
        is_ok, _ = mgr.check_connection()
        if not is_ok:
            ui.notify("Ollama 不可用。", type="negative")
            return
        try:
            ok_del, msg = mgr.delete_model(name)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        ui.notify(msg, type="positive" if ok_del else "negative")
        ui.navigate.to("/models")

    with ui.element("div").classes("max-w-6xl mx-auto p-8"):
        with ui.element("div").classes("mb-8"):
            ui.label("模型管理").classes("text-2xl font-bold text-slate-900")
        _content()
