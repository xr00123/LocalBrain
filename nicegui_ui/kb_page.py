from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from nicegui import run, ui

from config import SETTINGS
from core.kb_manager import KBManager


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

    with ui.element("div").classes("flex-1 min-h-0 w-full max-w-6xl mx-auto p-8 flex flex-col overflow-hidden"):
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

        # Dashboard
        dashboard_container = ui.element("div").classes("mt-6")

        def refresh_dashboard() -> None:
            dashboard_container.clear()
            kb_name = str(kb_select.value)
            try:
                rows = kbm.list_chunks(kb_name)
                doc_stats = kbm.doc_stats(rows)
                
                doc_count = len(doc_stats)
                chunk_count = len(rows)
                kb_count = len(collections)
                embed_model = SETTINGS.embedding_model

                with dashboard_container:
                    with ui.element("div").classes("grid grid-cols-1 md:grid-cols-4 gap-6"):
                        with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                            ui.label("文档数量").classes("text-sm text-gray-500 font-medium")
                            ui.label(str(doc_count)).classes("text-3xl font-bold text-slate-900 mt-2")
                        
                        with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                            ui.label("切片总数").classes("text-sm text-gray-500 font-medium")
                            ui.label(str(chunk_count)).classes("text-3xl font-bold text-slate-900 mt-2")
                            
                        with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                            ui.label("知识库总数").classes("text-sm text-gray-500 font-medium")
                            ui.label(str(kb_count)).classes("text-3xl font-bold text-slate-900 mt-2")
                            
                        with ui.card().classes("rounded-xl shadow-sm border border-gray-200 bg-white p-6"):
                            ui.label("Embedding 模型").classes("text-sm text-gray-500 font-medium")
                            ui.label(embed_model).classes("text-lg font-bold text-slate-900 mt-2 truncate").props(f"title={embed_model}")
            except Exception as ex:
                ui.notify(f"刷新看板失败: {ex}", type="negative")

        refresh_dashboard()
        kb_select.on("update:model-value", lambda _: refresh_dashboard())

        with ui.tabs().classes("w-full mt-6") as tabs:
            tab_units = ui.tab("单元")
            tab_recall = ui.tab("命中测试")
            tab_chunks = ui.tab("分段预览")

        with ui.tab_panels(tabs, value=tab_units).classes("w-full mt-4 bg-transparent flex-1 min-h-0 overflow-hidden"):
            # Tab 1: 单元 (Units)
            with ui.tab_panel(tab_units).classes("p-0 h-full min-h-0 overflow-y-auto"):
                with ui.element("div").classes("grid grid-cols-1 lg:grid-cols-3 gap-6"):
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

                        async def on_upload(e) -> None:
                            try:
                                # Check for new NiceGUI version (UploadEventArguments has .file)
                                if hasattr(e, 'file'):
                                    content = await e.file.read()
                                    uploads.append(_InMemoryUpload(name=e.file.name, data=content))
                                else:
                                    # Fallback for older versions
                                    uploads.append(_InMemoryUpload(name=e.name, data=e.content.read()))
                            except Exception as ex:
                                ui.notify(f"上传失败: {ex}", type="negative")

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
                            # Refresh grid and stay on same page
                            refresh_grid()

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
                                with ui.element("div").classes("flex flex-col gap-3"):
                                    for row in stats:
                                        filename = str(row.get("文件名") or "").strip()
                                        chunks = int(row.get("切片数量") or 0)
                                        if not filename:
                                            continue
                                        with ui.card().classes(
                                            "w-full rounded-xl shadow-sm border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow duration-200 group relative flex-row items-center gap-4"
                                        ):
                                            # File Icon & Name
                                            with ui.row().classes("items-center gap-3 flex-1 min-w-0"):
                                                with ui.element("div").classes("p-2 rounded-lg bg-indigo-50 flex-none flex items-center justify-center"):
                                                    ui.icon(_file_icon(filename)).classes("text-indigo-500 text-xl")
                                                
                                                ui.label(filename).classes(
                                                    "font-semibold text-slate-800 truncate text-sm"
                                                ).props(f"title='{filename}'")

                                            # Stats & Actions
                                            with ui.row().classes("items-center gap-6 flex-none"):
                                                # Chunks count
                                                with ui.row().classes("items-center gap-1.5 text-xs text-gray-500"):
                                                    ui.icon("layers").classes("text-xs")
                                                    ui.label(f"{chunks} 切片")
                                                
                                                # Status badge
                                                with ui.row().classes("items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-100"):
                                                    ui.element("div").classes("w-1.5 h-1.5 rounded-full bg-green-500")
                                                    ui.label("已索引").classes("text-xs")

                                                # Delete button
                                                ui.button(
                                                    icon="delete",
                                                    on_click=lambda f=filename: _delete_file(kb_select.value, f),
                                                ).props("flat round dense size=sm").classes(
                                                    "text-gray-400 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                                                )

                        kb_select.on("update:model-value", lambda e: refresh_grid())
                        refresh_grid()

            # Tab 2: 命中测试 (Recall Test)
            with ui.tab_panel(tab_recall).classes("p-0 h-full min-h-0 flex flex-col"):
                # Use a container to limit max-width, matching the grid layout above (which is max-w-6xl mx-auto)
                # Since we are inside a tab panel which is inside a tab panels container which is inside a max-w-6xl container,
                # we just need to make sure this card fills the available width.
                # The issue might be that the card is not taking full width or has weird margins.
                # Let's ensure it spans the full width of the parent tab panel.
                with ui.card().classes("w-full rounded-xl shadow-sm border border-gray-200 bg-white p-6 h-full min-h-0 flex flex-col"):
                    ui.label("命中测试").classes("font-bold text-slate-900")
                    ui.label("输入问题，测试知识库的召回效果。").classes("text-sm text-gray-500 font-medium mt-1")

                    with ui.row().classes("w-full gap-4 mt-6 flex-none"):
                        test_input = ui.input(label="测试问题").props("outlined").classes("flex-grow")
                        top_k = ui.number(label="Top K", value=4, min=1, max=20, step=1).props("outlined").classes("w-24")
                        ui.button("测试", on_click=lambda: run_hit_test()).classes(
                            "bg-black text-white rounded-lg px-6 h-[56px] hover:bg-gray-800"
                        )
                        
                    # Scrollable results area
                    results_scroll = ui.scroll_area().classes("mt-6 flex-1 min-h-0 w-full pr-4 border-t border-gray-100 pt-4")
                    with results_scroll:
                        results_container = ui.element("div").classes("flex flex-col gap-4 w-full")

                    def run_hit_test():
                        question = test_input.value
                        if not question:
                            ui.notify("请输入测试问题", type="warning")
                            return
                        
                        results_container.clear()
                        with results_container:
                            ui.spinner("dots").classes("mx-auto my-4")
                        
                        try:
                            results = kbm.hit_test(
                                collection_name=kb_select.value,
                                question=question,
                                k=int(top_k.value),
                                embedding_model=SETTINGS.embedding_model,
                            )
                            results_container.clear()
                            
                            if not results:
                                with results_container:
                                    ui.label("未召回到相关内容。").classes("text-gray-500 italic")
                                return

                            with results_container:
                                for i, r in enumerate(results):
                                    with ui.card().classes("w-full border border-gray-200 p-0 rounded-xl bg-white overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-200"):
                                        # Header: Metadata
                                        with ui.row().classes("items-center justify-between w-full px-4 py-3 bg-gray-50 border-b border-gray-100"):
                                            with ui.row().classes("items-center gap-3"):
                                                # Rank Badge
                                                with ui.element("div").classes(
                                                    "flex items-center justify-center w-6 h-6 rounded-full bg-indigo-600 text-white text-xs font-bold shadow-sm"
                                                ):
                                                    ui.label(str(i+1))
                                                
                                                # Similarity Score
                                                with ui.row().classes("items-baseline gap-1.5"):
                                                    ui.label("相似度").classes("text-xs text-gray-500 font-medium")
                                                    ui.label(f"{r.get('similarity', 0):.4f}").classes("text-sm text-indigo-600 font-mono font-bold")
                                                
                                                # Distance Score
                                                with ui.row().classes("items-baseline gap-1.5 pl-2 border-l border-gray-300/50"):
                                                    ui.label("距离").classes("text-xs text-gray-400 font-medium")
                                                    ui.label(f"{r.get('distance', 0):.4f}").classes("text-xs text-gray-500 font-mono")

                                            # Source File Badge
                                            with ui.row().classes("items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-gray-200 shadow-sm"):
                                                ui.icon("description").classes("text-xs text-gray-400")
                                                ui.label(r.get("source", "未知来源")).classes("text-xs text-gray-600 font-medium max-w-[150px] truncate").props(f"title='{r.get('source', '')}'")

                                        # Content Body
                                        with ui.element("div").classes("p-4"):
                                            content = r.get("content", "")
                                            ui.markdown(content).classes("text-sm text-slate-700 leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2")
                        except Exception as e:
                            results_container.clear()
                            ui.notify(f"测试失败: {e}", type="negative")

            # Tab 3: 分段预览 (Chunk View)
            with ui.tab_panel(tab_chunks).classes("p-0 h-full min-h-0 flex flex-col"):
                with ui.card().classes("w-full rounded-xl shadow-sm border border-gray-200 bg-white p-6 h-full min-h-0 flex flex-col"):
                    ui.label("分段预览").classes("font-bold text-slate-900")
                    #ui.label("查看知识库中的所有切片详情。").classes("text-sm text-gray-500 font-medium mt-1")

                    chunk_list_container = ui.element("div").classes("w-full mt-6 flex-1 min-h-0 flex flex-col overflow-hidden")

                    async def load_chunks():
                        chunk_list_container.clear()
                        with chunk_list_container:
                            ui.spinner("dots").classes("mx-auto my-4")
                        
                        try:
                            # Use run.io_bound to avoid blocking the UI thread during data fetching
                            rows = await run.io_bound(kbm.list_chunks, str(kb_select.value))
                            
                            chunk_list_container.clear()
                            if not rows:
                                with chunk_list_container:
                                    ui.label("当前知识库无数据").classes("text-gray-500 italic")
                                return

                            # Get unique filenames
                            filenames = sorted(list(set(r.source for r in rows)))
                            
                            with chunk_list_container:
                                with ui.row().classes("w-full gap-4 mb-4 flex-none items-center"):
                                    file_filter = ui.select(
                                        ["所有文件"] + filenames,
                                        value="所有文件",
                                        #label="筛选文件",
                                    ).props("outlined dense options-dense").classes("w-64")

                                    ui.label(f"共 {len(rows)} 个切片").classes("text-sm text-gray-500 ml-auto")

                                    ui.button(icon="refresh", on_click=load_chunks).props("flat round dense").tooltip("刷新列表")

                                chunk_table_container = ui.element("div").classes("w-full flex-1 min-h-0 relative overflow-hidden flex flex-col")

                                def filter_chunks():
                                    selected_file = file_filter.value
                                    chunk_table_container.clear()

                                    filtered_rows = []
                                    for r in rows:
                                        if selected_file != "所有文件" and r.source != selected_file:
                                            continue
                                        filtered_rows.append(r)

                                    filtered_rows.reverse()

                                    with chunk_table_container:
                                        with ui.scroll_area().classes("h-full w-full").props("content-style='width: 100%'"):
                                            with ui.element("div").classes(
                                                "w-full flex flex-col gap-3 pb-4"
                                            ):
                                                for r in filtered_rows[:100]:
                                                    with ui.card().classes(
                                                        "w-full border border-gray-200 p-4 rounded-xl shadow-sm hover:shadow-md transition-all flex-none bg-white group"
                                                    ):
                                                        # Header
                                                        with ui.row().classes("justify-between mb-3 items-center w-full pb-3 border-b border-gray-100"):
                                                            # File info with hover effect
                                                            with ui.row().classes("items-center gap-2 cursor-pointer opacity-80 hover:opacity-100 transition-opacity").on(
                                                                "click", lambda _, s=r.source: file_filter.set_value(s)
                                                            ):
                                                                with ui.element("div").classes("p-1.5 rounded-md bg-indigo-50 text-indigo-500"):
                                                                    ui.icon("description").classes("text-xs")
                                                                ui.label(r.source).classes(
                                                                    "font-bold text-sm text-slate-800 hover:text-indigo-600 transition-colors"
                                                                ).tooltip("点击筛选此文件")
                                                            
                                                            # Meta info
                                                            with ui.row().classes("items-center gap-3"):
                                                                ui.label(f"ID: {r.chunk_index}").classes(
                                                                    "font-mono text-[10px] text-gray-400 bg-gray-50 px-2 py-1 rounded"
                                                                )
                                                                # Copy button
                                                                ui.button(
                                                                    icon="content_copy",
                                                                    on_click=lambda _, c=r.content: (ui.run_javascript(f"navigator.clipboard.writeText(`{c}`)"), ui.notify("已复制内容", type="positive"))
                                                                ).props("flat round dense size=xs").classes("text-gray-300 hover:text-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity")

                                                        # Content
                                                        with ui.element("div").classes("relative"):
                                                            ui.markdown(r.content).classes("text-sm text-slate-600 leading-relaxed")

                                                if len(filtered_rows) > 100:
                                                    ui.label(
                                                        f"仅显示前 100 条 (共 {len(filtered_rows)} 条匹配)"
                                                    ).classes("text-center text-xs text-gray-400 py-2")
                                                elif not filtered_rows:
                                                    ui.label("未找到匹配切片").classes("text-center text-gray-400 py-4")

                                file_filter.on("update:model-value", filter_chunks)
                                filter_chunks()

                        except Exception as e:
                            chunk_list_container.clear()
                            with chunk_list_container:
                                ui.label(f"加载失败: {e}").classes("text-red-500")
                            ui.notify(f"加载切片失败: {e}", type="negative")

                    # Load chunks when tab is active
                    async def on_tab_change(e):
                        if e.value == "分段预览":
                            await load_chunks()
                    
                    tabs.on_value_change(on_tab_change)

                    async def on_kb_change_chunks(e):
                        if tabs.value == "分段预览":
                            await load_chunks()

                    kb_select.on("update:model-value", on_kb_change_chunks)
