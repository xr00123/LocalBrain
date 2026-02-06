from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from nicegui import app, run, ui

from LocalBrain.config import SETTINGS
from LocalBrain.core.kb_manager import KBManager
from LocalBrain.core.model_manager import ModelManager
from LocalBrain.core.processor import get_vectorstore


def _to_lc_messages(history: List[Dict[str, str]]) -> list:
    msgs = [SystemMessage(content="你是一个离线本地助手，回答要简洁准确。")]
    for m in history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    return msgs


def _build_llm(model: str, temperature: float, max_tokens: int) -> ChatOllama:
    kwargs: Dict[str, Any] = {"model": model, "temperature": float(temperature)}
    if max_tokens:
        kwargs["num_predict"] = int(max_tokens)
    try:
        return ChatOllama(**kwargs)
    except TypeError:
        return ChatOllama(model=model)


async def _stream_llm_text(llm: Any, prompt_input: Any) -> Any:
    q: asyncio.Queue[Optional[str]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _worker() -> None:
        try:
            stream_fn = getattr(llm, "stream", None)
            if not callable(stream_fn):
                result = llm.invoke(prompt_input)
                text = getattr(result, "content", str(result))
                if text:
                    loop.call_soon_threadsafe(q.put_nowait, str(text))
                return
            for chunk in stream_fn(prompt_input):
                text = getattr(chunk, "content", None)
                if text:
                    loop.call_soon_threadsafe(q.put_nowait, str(text))
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, f"\n\n[生成失败：{str(e)}]")
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=_worker, daemon=True).start()
    while True:
        item = await q.get()
        if item is None:
            break
        yield item


def chat_page_content() -> None:
    mgr = ModelManager()
    kbm = KBManager()

    try:
        model_names = [m["name"] for m in mgr.list_models()] or [SETTINGS.llm_model]
    except Exception:
        model_names = [SETTINGS.llm_model]

    try:
        collections = kbm.list_collections()
    except Exception:
        collections = []
    collection_options = ["（不使用知识库）", *collections]

    store = app.storage.user
    store.setdefault("chat_messages", [])
    store.setdefault("chat_model", model_names[0] if model_names else SETTINGS.llm_model)
    store.setdefault("chat_kb", collection_options[0])
    store.setdefault("chat_temperature", 0.2)
    store.setdefault("chat_max_tokens", 2048)

    def _get_messages() -> List[Dict[str, str]]:
        raw = store.get("chat_messages") or []
        return list(raw) if isinstance(raw, list) else []

    def _set_messages(msgs: List[Dict[str, str]]) -> None:
        store["chat_messages"] = msgs

    def _scroll_to_bottom() -> None:
        ui.run_javascript(
            "const el=document.getElementById('chat-scroll'); if(el){el.scrollTop=el.scrollHeight;}"
        )

    prompt_in = None
    messages_container = None
    last_response_ui: Optional[ui.markdown] = None
    model_select = None
    kb_select = None
    temp_toggle = None
    tokens_input = None

    @ui.refreshable
    def render_messages_wrapper() -> None:
        nonlocal last_response_ui
        last_response_ui = None
        msgs = _get_messages()
        for i, m in enumerate(msgs):
            role = m.get("role")
            content = m.get("content", "")
            is_last = (i == len(msgs) - 1)
            
            if role == "user":
                with ui.row().classes("w-full justify-end gap-4"):
                    with ui.element("div").classes("flex-grow min-w-0 flex justify-end"):
                        with ui.element("div").classes(
                            "text-slate-800 px-0 py-1 max-w-full leading-relaxed"
                        ):
                            ui.markdown(content).classes("prose prose-sm max-w-none text-slate-800 [&_p]:my-0")
                    
                    with ui.element("div").classes("flex-shrink-0"):
                        with ui.element("div").classes("w-8 h-8 rounded-lg bg-slate-200 flex items-center justify-center border border-slate-300"):
                            ui.icon("person", size="18px").classes("text-slate-600")
            else:
                with ui.row().classes("w-full justify-start gap-4"):
                    with ui.element("div").classes("flex-shrink-0 mt-1"):
                        with ui.element("div").classes("w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100"):
                            ui.icon("smart_toy", size="18px").classes("text-indigo-600")
                    
                    with ui.element("div").classes("flex-grow min-w-0"):
                        ui.label(store.get("chat_model", "助手")).classes("text-xs font-bold text-slate-400 mb-1 ml-1")
                        
                        if not content and role == "assistant" and is_last:
                            with ui.row().classes("items-center gap-2 h-8"):
                                ui.spinner("dots", size="24px", color="indigo-400")
                                ui.label("思考中...").classes("text-xs text-slate-400 font-medium animate-pulse")
                            last_response_ui = None
                        else:
                            md = ui.markdown(content).classes(
                                "prose prose-slate prose-sm max-w-none "
                                "prose-headings:font-bold prose-headings:text-slate-900 "
                                "prose-p:text-slate-700 prose-p:leading-7 "
                                "prose-pre:bg-slate-900 prose-pre:text-slate-200 prose-pre:font-mono "
                                "prose-code:font-mono prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:rounded"
                            )
                            if role == "assistant" and is_last:
                                last_response_ui = md
        _scroll_to_bottom()

    async def send(_: Any = None) -> None:
        question = (prompt_in.value or "").strip()
        if not question:
            return
        if model_select:
            store["chat_model"] = model_select.value
        if kb_select:
            store["chat_kb"] = kb_select.value
        if temp_toggle:
            store["chat_temperature"] = temp_toggle.value
        if tokens_input:
            store["chat_max_tokens"] = int(tokens_input.value or 2048)

        msgs = _get_messages()
        msgs.append({"role": "user", "content": question})
        prompt_in.value = ""
        
        msgs.append({"role": "assistant", "content": ""})
        _set_messages(msgs)
        
        render_messages_wrapper.refresh()
        await asyncio.sleep(0)
        llm = _build_llm(
            store["chat_model"],
            temperature=store["chat_temperature"],
            max_tokens=store["chat_max_tokens"],
        )
        msgs_for_llm = msgs[:-1]
        
        context = ""
        if store["chat_kb"] != "（不使用知识库）":
            try:
                vs = get_vectorstore(
                    collection_name=store["chat_kb"], embedding_model=SETTINGS.embedding_model
                )
                docs = await run.io_bound(vs.similarity_search, question, k=SETTINGS.retrieval_k)
                context = "\n\n".join(
                    [
                        f"[{i+1}] {d.metadata.get('source','未知来源')}"
                        + (f"（第 {d.metadata.get('page')} 页）" if d.metadata.get("page") else "")
                        + f"\n{d.page_content}"
                        for i, d in enumerate(docs)
                    ]
                )
            except Exception as e:
                context = f"检索知识库失败：{str(e)}"

        final_prompt_input = []
        if context:
            sys_tmpl = "你是本地知识库问答助手。只使用给定上下文回答；若上下文不足，直接说不知道。"
            human_tmpl = "问题：{question}\n\n上下文：\n{context}"
            prompt_tmpl = ChatPromptTemplate.from_messages([("system", sys_tmpl), ("human", human_tmpl)])
            final_prompt_input = prompt_tmpl.format_messages(question=question, context=context)
        else:
            final_prompt_input = _to_lc_messages(msgs_for_llm)

        current_content = ""
        streamed_any = False
        async for delta in _stream_llm_text(llm, final_prompt_input):
            if not delta:
                continue
            streamed_any = True
            is_first_token = current_content == ""
            current_content += delta
            if is_first_token:
                msgs[-1]["content"] = current_content + " ▍"
                render_messages_wrapper.refresh()
            elif last_response_ui:
                last_response_ui.set_content(current_content + " ▍")
            await asyncio.sleep(0)
        
        if last_response_ui:
            last_response_ui.set_content(current_content)
        elif current_content or streamed_any:
            msgs[-1]["content"] = current_content
            render_messages_wrapper.refresh()
        
        msgs[-1]["content"] = current_content
        _set_messages(msgs)
        _scroll_to_bottom()

    with ui.row().classes(
        "h-16 w-full items-center justify-between px-8 border-b border-slate-100 bg-white sticky top-0 z-40"
    ):
        with ui.row().classes("items-center gap-2"):
            ui.label("对话").classes("text-slate-400 text-sm font-medium")
            ui.icon("chevron_right").classes("text-slate-300 text-xs")
            ui.label("当前会话").classes("text-slate-700 text-sm font-semibold")
        
        with ui.element("div").classes("relative z-50"):
            # 点击外部关闭的遮罩层
            # 当菜单打开时，覆盖全屏的透明层
            settings_overlay = ui.element("div").classes(
                "fixed inset-0 z-40 bg-transparent hidden"
            )
            
            # 设置面板
            # 使用 invisible 和 opacity 控制显示，确保 DOM 预渲染
            settings_panel = ui.element("div").classes(
                "absolute top-full right-0 mt-2 w-80 p-5 bg-white rounded-xl shadow-xl border border-slate-100 z-50 origin-top-right transition-all duration-200 ease-out opacity-0 invisible scale-95"
            )
            
            def toggle_settings():
                is_hidden = "hidden" in settings_overlay.classes
                if is_hidden:
                    # 打开菜单
                    settings_overlay.classes(remove="hidden")
                    settings_panel.classes(remove="opacity-0 invisible scale-95", add="opacity-100 visible scale-100")
                else:
                    # 关闭菜单
                    settings_overlay.classes(add="hidden")
                    settings_panel.classes(remove="opacity-100 visible scale-100", add="opacity-0 invisible scale-95")

            settings_overlay.on("click", toggle_settings)

            with ui.button(on_click=toggle_settings).props("flat no-caps").classes(
                "rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-1.5 transition-all shadow-sm border border-slate-200/50"
            ):
                ui.label(store["chat_model"]).classes("text-xs font-bold tracking-wide text-indigo-600")
                ui.label("|").classes("mx-2 text-slate-300 text-xs")
                ui.icon("tune").classes("text-slate-500 text-xs")
            
            with settings_panel:
                ui.label("对话设置").classes("text-xs font-bold text-slate-400 uppercase tracking-wider mb-4")
                
                ui.label("模型").classes("text-xs font-medium text-slate-500 mb-1")
                model_select = ui.select(model_names, value=store["chat_model"]).props(
                    "outlined dense rounded color=indigo"
                ).classes("w-full mb-4")
                
                ui.label("知识库").classes("text-xs font-medium text-slate-500 mb-1")
                kb_select = ui.select(collection_options, value=store["chat_kb"]).props(
                    "outlined dense rounded color=indigo"
                ).classes("w-full mb-4")
                
                ui.label("回答风格").classes("text-xs font-medium text-slate-500 mb-1")
                temp_toggle = ui.toggle(
                    {0.2: "精准", 0.5: "平衡", 0.8: "创意"},
                    value=store["chat_temperature"]
                ).props("spread no-caps unelevated toggle-color=indigo").classes("w-full mb-4 border border-slate-200 rounded-lg overflow-hidden")
                
                ui.label("最大输出 Token").classes("text-xs font-medium text-slate-500 mb-1")
                tokens_input = ui.number(value=store["chat_max_tokens"], min=128, max=32768, step=128).props(
                    "outlined dense rounded color=indigo"
                ).classes("w-full mb-4")
                
                ui.separator().classes("mb-4")
                
                with ui.button(on_click=lambda: (_set_messages([]), render_messages_wrapper.refresh())).props("flat no-caps").classes("w-full text-red-500 hover:bg-red-50 rounded-lg"):
                    ui.icon("delete_outline").classes("mr-2")
                    ui.label("清空对话")

    # 强制注入隐藏滚动条的样式，确保优先级最高
    # 注意：在 SPA 模式下，这些样式只需注入一次，但为了保险起见保留在这里，或者移动到 layout 中
    # 为了避免重复注入，可以检查是否已注入，或者就留在这里，nicegui 会处理
    ui.add_head_html(
        """
        <style>
            #chat-scroll {
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
            }
            #chat-scroll::-webkit-scrollbar {
                display: none !important;
                width: 0 !important;
                height: 0 !important;
                background: transparent !important;
            }
            
            /* 强制重置输入框样式，消除底部溢出 */
            .chat-input {
                margin: 0 !important;
                padding: 0 !important;
            }
            .chat-input .q-field__control {
                height: auto !important;
                min-height: 0 !important;
                padding: 0 !important;
            }
            .chat-input .q-field__control:before,
            .chat-input .q-field__control:after {
                display: none !important;
            }
            .chat-input textarea {
                padding: 12px 16px !important;
                margin: 0 !important;
            }
        </style>
        """
    )

    with ui.element("div").classes("flex-1 min-h-0 w-full flex flex-col"):
        messages_container = ui.column().props("id=chat-scroll").classes(
            "no-scrollbar flex-1 min-h-0 w-full max-w-[800px] mx-auto px-6 py-8 pb-48 space-y-10 overflow-y-auto"
        )
        with messages_container:
            render_messages_wrapper()

    with ui.column().classes(
        "fixed bottom-8 left-[260px] right-0 z-50 pointer-events-none flex items-center justify-center"
    ):
        with ui.row().classes(
            "w-full max-w-[800px] bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.12)] border border-slate-100 p-2 items-center pointer-events-auto transition-all focus-within:shadow-[0_8px_40px_rgb(79,70,229,0.15)] focus-within:border-indigo-500/30"
        ):
            prompt_in = ui.textarea(placeholder="发送消息给 LocalBrain...").props(
                "borderless autogrow rows=1 hide-bottom-space"
            ).classes(
                "chat-input flex-grow text-slate-700 text-base max-h-40 overflow-y-auto placeholder-slate-400 focus:outline-none"
            ).on("keydown.enter.prevent", send)
            
            ui.button(icon="arrow_upward", on_click=send).props(
                "round flat dense"
            ).classes("text-white bg-indigo-600 hover:bg-indigo-700 shadow-md transform hover:scale-105 transition-all duration-200")
