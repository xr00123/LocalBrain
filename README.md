# LocalBrain

LocalBrain 是一个基于本地大模型的知识库问答与聊天系统，采用 Python 和 [NiceGUI](https://nicegui.io/) 构建，界面设计参考了现代 SaaS 软件（如 Linear 和 ChatGPT）的审美风格。

## 项目特点

- **现代 UI 设计**：
  - 采用 Tailwind CSS 构建的响应式三栏布局（侧边导航、核心对话区、右侧设置面板）。
  - 精心设计的消息气泡与交互体验。
  - 底部悬浮输入框，支持 backdrop-blur 效果。
- **本地模型支持**：支持加载和运行本地 LLM（通过 `core/model_manager.py` 管理）。
- **知识库管理**：支持上传和管理本地文档，构建 RAG（检索增强生成）应用。

## 环境要求

- Python 3.8+
- 操作系统：Windows / macOS / Linux

## 快速开始

### 1. 安装依赖

在项目根目录下运行以下命令安装所需依赖：

```bash
pip install -r requirements.txt
```

### 2. 启动项目

运行主应用程序脚本：

```bash
python nicegui_app.py
```

### 3. 访问应用

项目启动后，终端会显示访问地址。默认情况下，请在浏览器中访问：

http://localhost:8503

## 项目结构

- `nicegui_app.py`: 应用程序入口。
- `nicegui_ui/`: UI 页面与组件逻辑。
  - `chat_page.py`: 核心聊天页面实现。
  - `layout.py`: 全局布局与样式定义。
- `core/`: 核心后端逻辑（模型管理、RAG 引擎等）。
