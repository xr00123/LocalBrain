from __future__ import annotations

import ctypes
import shutil
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from nicegui import ui

from LocalBrain.core.model_manager import ModelManager


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
                    ui.label("暂无本地模型。").classes("text-sm text-gray-500 font-medium mt-4")
                else:
                    header = ui.element("div").classes(
                        "mt-6 grid grid-cols-12 gap-3 text-sm text-gray-500 font-medium"
                    )
                    with header:
                        ui.label("模型名").classes("col-span-5")
                        ui.label("大小").classes("col-span-2")
                        ui.label("家族").classes("col-span-2")
                        ui.label("参数量").classes("col-span-2")
                        ui.label("操作").classes("col-span-1")

                    for m in models:
                        row = ui.element("div").classes(
                            "grid grid-cols-12 gap-3 items-center py-2 border-b border-gray-200/70"
                        )
                        with row:
                            ui.label(m["name"]).classes("col-span-5 text-sm text-slate-900 font-medium truncate")
                            ui.label(m["size"]).classes("col-span-2 text-sm text-gray-500 font-medium")
                            ui.label(m["family"]).classes("col-span-2 text-sm text-gray-500 font-medium")
                            ui.label(m["params"]).classes("col-span-2 text-sm text-gray-500 font-medium")
                            ui.button(
                                icon="delete",
                                on_click=lambda name=m["name"]: _delete_model(name),
                            ).props("flat").classes(
                                "col-span-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
                            )

            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6 lg:col-span-1"):
                ui.label("下载专区").classes("font-bold text-slate-900")
                ui.label("输入模型名称后开始下载。").classes("text-sm text-gray-500 font-medium mt-1")

                dl = mgr.get_download_status()
                status = dl.get("status")
                if status == "running":
                    m_name = dl.get("model_name") or "未知模型"
                    percent = float(dl.get("percent") or 0.0)
                    msg = dl.get("message") or ""
                    ui.label(f"正在后台下载：{m_name}").classes("text-sm text-slate-900 font-medium mt-4")
                    ui.linear_progress(value=percent).classes("h-2 rounded-full mt-3")
                    if msg:
                        ui.label(msg).classes("text-xs text-gray-500 font-medium mt-2")
                    ui.timer(1.0, lambda: ui.navigate.to("/models"), once=True)
                elif status == "success":
                    ui.label(f"下载完成：{dl.get('model_name')}").classes(
                        "text-sm text-slate-900 font-medium mt-4"
                    )
                    ui.button(
                        "完成",
                        on_click=lambda: (_clear_download(), ui.navigate.to("/models")),
                    ).classes("mt-4 bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800 w-full")
                elif status == "error":
                    ui.label("下载失败").classes("text-sm text-slate-900 font-medium mt-4")
                    ui.label(str(dl.get("message") or "")).classes("text-xs text-gray-500 font-medium mt-2")
                    ui.button(
                        "清除状态",
                        on_click=lambda: (_clear_download(), ui.navigate.to("/models")),
                    ).classes("mt-4 bg-gray-100 text-gray-900 rounded-lg hover:bg-gray-200 px-4 py-2 w-full")
                else:
                    name_in = ui.input(
                        placeholder="例如: deepseek-r1:7b, llama3.1, qwen2.5:7b",
                        label="模型名称",
                    ).classes("mt-5 w-full rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500")
                    btn = ui.button(
                        "立即下载",
                        on_click=lambda: _start_download(ok, name_in.value),
                    ).classes("mt-4 bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800 w-full")
                    if not ok:
                        btn.disable()
                        ui.label("Ollama 不可用，无法下载模型。").classes(
                            "text-xs text-gray-500 font-medium mt-2"
                        )

    def _delete_model(name: str) -> None:
        if not ok:
            ui.notify("Ollama 不可用。", type="negative")
            return
        try:
            ok_del, msg = mgr.delete_model(name)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        ui.notify(msg, type="positive" if ok_del else "negative")
        ui.navigate.to("/models")

    def _clear_download() -> None:
        try:
            mgr.clear_download_status()
        except Exception:
            pass

    def _start_download(is_ok: bool, name: str) -> None:
        n = str(name or "").strip()
        if not n:
            ui.notify("请输入模型名称。", type="warning")
            return
        if not is_ok:
            ui.notify("Ollama 不可用。", type="negative")
            return
        ok_start, start_msg = mgr.start_pull_model_thread(n)
        ui.notify(start_msg, type="positive" if ok_start else "negative")
        ui.navigate.to("/models")

    with ui.element("div").classes("max-w-6xl mx-auto p-8"):
        with ui.element("div").classes("mb-8"):
            ui.label("模型管理").classes("text-2xl font-bold text-slate-900")
        _content()
