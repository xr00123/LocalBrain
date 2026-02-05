from __future__ import annotations

import os
import threading

# Fix for "Server disconnected" error on some systems (macOS) due to proxy interference
# Must be set BEFORE importing ollama/httpx to ensure it takes effect
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

import re
from typing import Dict, Generator, List, Optional, Tuple

import ollama


_download_state = {
    "model_name": None,
    "status": None,
    "percent": 0.0,
    "message": ""
}
_download_lock = threading.Lock()


def _format_gb(size_bytes: Optional[int]) -> str:
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        return "-"
    gb = size_bytes / (1024**3)
    return f"{gb:.2f} GB"


def _extract_params(name: str, details: Optional[Dict]) -> str:
    if details and isinstance(details, dict):
        ps = details.get("parameter_size")
        if ps:
            return str(ps)
    m = re.search(r":(\d+(?:\.\d+)?)\s*([bB])\b", name)
    if m:
        return f"{m.group(1)}{m.group(2).upper()}"
    return "-"


def _extract_family(name: str, details: Optional[Dict]) -> str:
    if details and isinstance(details, dict):
        fam = details.get("family")
        if fam:
            return str(fam)
        fams = details.get("families")
        if isinstance(fams, list) and fams:
            return str(fams[0])
    base = name.split(":")[0]
    base = base.split("/")[-1]
    return base or "-"


def _fmt_bytes(n: Optional[int]) -> str:
    if not isinstance(n, int) or n <= 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024.0 or u == units[-1]:
            return f"{f:.0f}{u}" if u == "B" else f"{f:.1f}{u}"
        f /= 1024.0
    return f"{n}B"


class ModelManager:
    def check_connection(self) -> Tuple[bool, str]:
        try:
            ollama.list()
            return True, ""
        except Exception as e:
            return False, str(getattr(e, "error", None) or e)

    def list_models(self) -> List[Dict]:
        data = ollama.list()
        
        # Normalize data to dict if it's a Pydantic object
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()
            
        items = data.get("models") if isinstance(data, dict) else None
        items = items or []

        models: List[Dict] = []
        for it in items:
            # Normalize item to dict if needed (though model_dump usually recurses)
            if hasattr(it, "model_dump"):
                it = it.model_dump()
            elif hasattr(it, "dict"):
                it = it.dict()

            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or it.get("model") or "").strip()
            if not name:
                continue
            size_bytes = it.get("size")
            details = it.get("details") if isinstance(it.get("details"), dict) else {}
            models.append(
                {
                    "name": name,
                    "size": _format_gb(size_bytes if isinstance(size_bytes, int) else None),
                    "family": _extract_family(name, details),
                    "params": _extract_params(name, details),
                }
            )
        models.sort(key=lambda x: x.get("name") or "")
        return models

    def delete_model(self, model_name: str) -> Tuple[bool, str]:
        try:
            ollama.delete(model_name)
            return True, f"已删除：{model_name}"
        except Exception as e:
            msg = str(getattr(e, "error", None) or e)
            return False, msg

    def get_download_status(self) -> Dict:
        """获取当前后台下载任务的状态"""
        with _download_lock:
            return _download_state.copy()

    def clear_download_status(self):
        """清除下载状态（通常在任务完成后调用）"""
        with _download_lock:
            _download_state.update({
                "model_name": None,
                "status": None,
                "percent": 0.0,
                "message": ""
            })

    def start_pull_model_thread(self, model_name: str) -> Tuple[bool, str]:
        """启动后台线程下载模型"""
        with _download_lock:
            if _download_state.get("status") == "running":
                current = _download_state.get("model_name")
                return False, f"已有正在进行的下载任务: {current}"
            
            _download_state.update({
                "model_name": model_name,
                "status": "running",
                "percent": 0.0,
                "message": "准备开始下载..."
            })
        
        thread = threading.Thread(target=self._pull_worker, args=(model_name,))
        thread.daemon = True
        thread.start()
        return True, "下载任务已启动"

    def _pull_worker(self, model_name: str):
        """后台下载工作线程"""
        try:
            for update in self.pull_model(model_name):
                with _download_lock:
                    _download_state.update({
                        "status": update["status"],
                        "percent": update["percent"],
                        "message": update["message"]
                    })
        except Exception as e:
            msg = str(getattr(e, "error", None) or e)
            with _download_lock:
                _download_state.update({
                    "status": "error",
                    "percent": 0.0,
                    "message": msg
                })

    def pull_model(self, model_name: str) -> Generator[Dict, None, None]:
        percent = 0.0
        try:
            stream = ollama.pull(model_name, stream=True)
            for part in stream:
                payload = part if isinstance(part, dict) else dict(part)
                status_text = str(payload.get("status") or "").strip()
                digest = str(payload.get("digest") or "").strip()
                total = payload.get("total")
                completed = payload.get("completed")
                if isinstance(total, int) and total > 0 and isinstance(completed, int) and completed >= 0:
                    percent = max(0.0, min(1.0, completed / total))

                if status_text.lower() == "success":
                    yield {"status": "success", "percent": 1.0, "message": "下载成功"}
                    return

                msg = status_text or "下载中"
                if digest:
                    msg = f"{msg} {digest}"
                if isinstance(total, int) and isinstance(completed, int) and total > 0:
                    msg = f"{msg} ({_fmt_bytes(completed)}/{_fmt_bytes(total)})"

                yield {"status": "running", "percent": percent, "message": msg}

            yield {"status": "success", "percent": 1.0, "message": "下载成功"}
        except Exception as e:
            msg = str(getattr(e, "error", None) or e)
            yield {"status": "error", "percent": percent, "message": msg}
