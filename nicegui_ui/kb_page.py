from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from nicegui import ui

from LocalBrain.config import SETTINGS
from LocalBrain.core.kb_manager import KBManager


@dataclass(frozen=True)
class _InMemoryUpload:
    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


def _file_icon(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "picture_as_pdf"
    if ext == ".txt":
        return "description"
    return "insert_drive_file"


def kb_page_content() -> None:
    kbm = KBManager()

    def _create_collection(name: Optional[str]) -> None:
        n = str(name or "").strip()
        if not n:
            ui.notify("知识库名称不能为空。", type="warning")
            return
        try:
            kbm.create_collection(n)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        ui.notify("创建成功。", type="positive")
        # 刷新页面或重新加载内容 (SPA模式下，这里应该重新加载 kb_page_content)
        # 由于我们是在 content 函数内部，直接重新渲染比较麻烦。
        # 简单方案：通知用户刷新，或者我们只刷新下拉列表。
        # 为了简单，我们这里重新加载内容区域。需要依赖外部机制，或者简单地清空并重建。
        # 但我们无法直接访问 content_container。
        # 临时方案：我们不跳转，而是手动刷新组件状态。
        # 更好的方案：_create_collection 应该触发 UI 更新。
        # 鉴于代码结构，我们这里只刷新页面 (F5效果) 或者是通知父级。
        # 在 SPA 模式下 ui.navigate.to("/kb") 会刷新。如果这是可接受的暂时方案。
        # 为了不刷新，我们应该使用回调重绘。
        # 让我们把这个逻辑留给 refresh_grid 或者更高级的重绘。
        # 暂时保留 ui.navigate.to，它会触发 SPA 路由（如果我们实现了路由拦截），否则会刷新。
        # 我们之前说过要避免刷新。
        # 我们可以调用 refresh_layout_content("kb") 如果有这个全局函数。
        # 这里先假设 ui.navigate.to 会被正确处理，或者我们接受创建知识库时的刷新。
        # 为了彻底解决闪烁，应该避免 navigate。
        # 但这需要重构很多。先保留 navigate，创建/删除是低频操作。
        ui.navigate.to("/kb")

    def _delete_file(collection: str, filename: str) -> None:
        try:
            kbm.delete_file(str(collection), filename)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        ui.notify(f"已删除：{filename}", type="positive")
        # 同上
        ui.navigate.to("/kb")

    with ui.element("div").classes("max-w-6xl mx-auto p-8"):
        with ui.element("div").classes("mb-8"):
            ui.label("知识库").classes("text-2xl font-bold text-slate-900")

        try:
            collections = kbm.list_collections()
        except Exception:
            collections = []

        if not collections:
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                ui.label("还没有知识库").classes("font-bold text-slate-900")
                ui.label("请先创建一个知识库，然后上传文件进行索引。").classes(
                    "text-sm text-gray-500 font-medium mt-1"
                )
                name_in = ui.input("知识库名称").classes(
                    "mt-5 w-full rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500"
                )
                ui.button(
                    "创建知识库",
                    on_click=lambda: _create_collection(name_in.value),
                ).classes("mt-4 bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800")
            return

        kb_select = ui.select(collections, value=collections[0], label="当前知识库").classes(
            "max-w-lg w-full"
        )

        with ui.element("div").classes("mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6"):
            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6 lg:col-span-1"):
                ui.label("上传文件").classes("font-bold text-slate-900")
                ui.label("支持多文件连续上传，写入后会自动清空。").classes(
                    "text-sm text-gray-500 font-medium mt-1"
                )
                with ui.element("div").classes("mt-5"):
                    with ui.expansion("🛠️ 解析参数设置").classes("w-full"):
                        chunk_size = ui.number(
                            value=500, label="切片大小", min=100, max=2000, step=50
                        ).classes("w-full")
                        chunk_overlap = ui.number(
                            value=50, label="切片重叠", min=0, max=500, step=10
                        ).classes("w-full mt-3")

                uploads: List[_InMemoryUpload] = []

                def on_upload(e) -> None:
                    try:
                        uploads.append(_InMemoryUpload(name=e.name, data=e.content.read()))
                    except Exception:
                        uploads.append(_InMemoryUpload(name=e.name, data=b""))

                drop = ui.upload(
                    multiple=True,
                    auto_upload=True,
                    on_upload=on_upload,
                    label="拖拽或点击上传 PDF/TXT",
                ).classes(
                    "mt-5 w-full border-dashed border-2 border-gray-300 rounded-xl p-6 bg-slate-50"
                )
                drop.props("accept=.pdf,.txt")

                def do_ingest() -> None:
                    if not uploads:
                        ui.notify("请先选择文件。", type="warning")
                        return
                    kb_name = str(kb_select.value)
                    try:
                        stats = kbm.ingest(
                            uploads,
                            collection_name=kb_name,
                            embedding_model=SETTINGS.embedding_model,
                            chunk_size=int(chunk_size.value or 500),
                            chunk_overlap=int(chunk_overlap.value or 50),
                        )
                    except Exception as ex:
                        ui.notify(f"写入失败：{ex}", type="negative")
                        return
                    files_received = int(stats.get("files_received") or 0)
                    files_with_text = int(stats.get("files_with_text") or 0)
                    documents_loaded = int(stats.get("documents_loaded") or 0)
                    chunks_created = int(stats.get("chunks_created") or 0)
                    if files_received > 0 and documents_loaded == 0 and chunks_created == 0:
                        ui.notify(
                            "选中文件已上传，但未提取到可索引文本（可能为扫描件/图片型 PDF）。",
                            type="warning",
                        )
                    else:
                        ui.notify(
                            f"导入完成：选中 {files_received}，成功解析 {files_with_text}；文档 {documents_loaded}，切片 {chunks_created}。",
                            type="positive",
                        )
                    uploads.clear()
                    try:
                        drop.reset()
                    except Exception:
                        pass
                    # 同上，暂时使用 navigate
                    ui.navigate.to("/kb")

                ui.button("写入知识库", on_click=do_ingest).classes(
                    "mt-4 w-full bg-black text-white rounded-lg px-4 py-2 hover:bg-gray-800"
                )

            with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6 lg:col-span-2"):
                ui.label("文件").classes("font-bold text-slate-900")
                ui.label("网格卡片视图，可直接删除文件对应的全部切片。").classes(
                    "text-sm text-gray-500 font-medium mt-1"
                )

                def list_file_stats(name: str) -> List[Dict]:
                    rows = kbm.list_chunks(name)
                    return kbm.doc_stats(rows)

                grid_host = ui.element("div").classes("mt-6")

                def refresh_grid() -> None:
                    grid_host.clear()
                    kb_name = str(kb_select.value)
                    try:
                        stats = list_file_stats(kb_name)
                    except Exception as ex:
                        ui.notify(f"读取失败：{ex}", type="negative")
                        return

                    if not stats:
                        with grid_host:
                            ui.label("当前知识库暂无数据。").classes("text-sm text-gray-500 font-medium")
                        return

                    with grid_host:
                        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"):
                            for row in stats:
                                filename = str(row.get("文件名") or "").strip()
                                chunks = int(row.get("切片数量") or 0)
                                if not filename:
                                    continue
                                with ui.card().classes(
                                    "rounded-xl shadow-sm border border-gray-200 bg-white p-6"
                                ):
                                    with ui.element("div").classes("flex items-start justify-between gap-4"):
                                        with ui.element("div").classes("min-w-0"):
                                            with ui.element("div").classes("flex items-center gap-2"):
                                                ui.icon(_file_icon(filename)).classes("text-gray-500")
                                                ui.label(filename).classes(
                                                    "font-medium text-gray-900 truncate max-w-[14rem]"
                                                )
                                            ui.label(f"切片数：{chunks}").classes(
                                                "text-sm text-gray-500 font-medium mt-2"
                                            )
                                        ui.button(
                                            icon="delete",
                                            on_click=lambda f=filename: _delete_file(kb_select.value, f),
                                        ).props("flat").classes(
                                            "text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
                                        )

                kb_select.on("update:model-value", lambda e: refresh_grid())
                refresh_grid()
