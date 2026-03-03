# 聊 (Liao)

基于视觉的 GUI 交互辅助工具，集成大语言模型。

聊 是一个使用 OCR 和大语言模型自动化桌面聊天应用的 Python 程序。它通过屏幕截图识别对话内容，生成上下文相关的回复，并模拟用户输入自动发送消息。

**支持平台：** Windows、Linux (X11/Wayland)

**支持的 LLM 后端：** Ollama（本地部署）、OpenAI API、Anthropic API 及任意 OpenAI 兼容接口

[English Documentation](README.md)

## 功能特性

- **基于视觉的自动化**：使用 OCR 读取聊天消息并检测界面元素
- **多种 LLM 后端**：支持 Ollama 本地推理、OpenAI、Anthropic 及兼容 API
- **双语界面**：中英文界面，支持运行时切换语言
- **聊天应用检测**：自动检测微信、QQ、Telegram、Slack、Discord 等应用
- **区域检测**：自动和手动的对话/输入区域检测，配有可视化覆盖层
- **回复门控**：等待对方回复后再生成并发送新消息
- **跨平台支持**：Windows 功能完整；Linux 通过 xdotool 和 Wayland ScreenCast 支持

## 安装

### 前置要求

**Python 版本：** 3.9 或更高

**LLM 后端：** 至少具备以下之一：
- [Ollama](https://ollama.ai/) 本地运行（推荐，保护隐私）
- OpenAI API 密钥
- Anthropic API 密钥
- 任意 OpenAI 兼容 API 接口

### Windows 安装

```bash
# 从 PyPI 安装
pip install liao

# 或安装带 OCR 支持的版本（推荐）
pip install liao[ocr]

# 或从源码安装
git clone https://github.com/cycleuser/Liao.git
cd Liao
pip install -r requirements.txt
```

### Linux 安装

Linux 需要额外的系统包以支持输入模拟和屏幕截图。

```bash
# 安装系统依赖
sudo apt install xdotool wl-clipboard xclip tesseract-ocr tesseract-ocr-chi-sim gnome-screenshot

# 可选：Wayland 屏幕截图支持（PyGObject 方案）
sudo apt install gstreamer1.0-plugins-good pipewire python3-gi python3-dbus

# 安装 Python 包
pip install liao

# 或从源码安装，使用 Linux 专用依赖
git clone https://github.com/cycleuser/Liao.git
cd Liao
pip install -r requirements-linux.txt
```

**注意**：xdotool 可用于大多数 Wayland 上的聊天应用，因为它们通常运行在 XWayland 兼容层下。

### OCR 引擎选择

聊 支持三种 OCR 引擎，请至少安装一种：

| 引擎 | 安装命令 | 说明 |
|------|---------|------|
| EasyOCR | `pip install easyocr` | 准确度最高，需要 PyTorch（约 2GB 下载） |
| RapidOCR | `pip install rapidocr-onnxruntime` | 轻量快速，仅支持 Python <3.13 |
| pytesseract | `pip install pytesseract` | 通用方案，需要 tesseract 程序 |

Linux 使用 pytesseract 时，需安装 tesseract 程序：
```bash
sudo apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
```

## 快速开始

### 启动图形界面

```bash
liao
# 或
python -m liao
```

### 命令行接口

```bash
# 列出可用窗口
liao list
liao list --chat-only

# 运行无头自动化
liao auto --title "微信" --model llama3 --rounds 5
```

## 使用指南

### 第一步：启动并连接 LLM

启动应用程序，配置 LLM 连接。输入 API 接口地址和模型名称。Ollama 使用 `http://localhost:11434`，云端 API 需输入 API 密钥。

![启动界面](images/1-开始界面.png)

### 第二步：配置语言（可选）

通过语言下拉菜单切换中英文界面。

![语言设置](images/2-设置中文.png)

### 第三步：选择模型

从可用选项中选择 LLM 模型。点击"刷新模型列表"更新可用模型。

![选择模型](images/3-选择模型.png)

### 第四步：选择目标窗口

点击"刷新窗口列表"列出打开的应用程序，双击选择目标聊天窗口。

![选择窗口](images/4-选择窗口.png)

### 第五步：配置聊天区域

点击"截图并检测"自动检测聊天和输入区域，或使用可视化覆盖层手动选择区域。

![设置区域](images/5-设置区域.png)

### 第六步：开始自动化

输入系统提示词定义助手人格，设置对话轮数，点击"开始自动对话"启动。

![开始对话](images/6-开始对话.png)

## 编程接口

```python
from liao import VisionAgent, LLMClientFactory
from liao.core import WindowManager

# 创建 LLM 客户端（Ollama 本地）
llm = LLMClientFactory.create_client(
    provider="ollama",
    base_url="http://localhost:11434",
    model="llama3"
)

# 查找目标窗口
wm = WindowManager()
window = wm.find_window_by_title("微信")

# 创建并运行代理
agent = VisionAgent(
    llm_client=llm,
    target_window=window,
    prompt="你是一个热情友好的朋友",
    max_rounds=10,
)

agent.run()
```

## 项目结构

```
Liao/
├── src/liao/
│   ├── __init__.py           # 版本号和公共 API
│   ├── api.py                # 公共 API (VisionAgent)
│   ├── cli.py                # CLI 入口点
│   ├── core/                 # 核心模块（窗口、截图、输入）
│   ├── llm/                  # LLM 客户端实现
│   ├── agent/                # 代理工作流和对话解析
│   ├── gui/                  # PySide6 GUI 组件
│   └── models/               # 数据模型
├── tests/                    # 单元测试
├── images/                   # 文档截图
├── requirements.txt          # 跨平台依赖
├── requirements-linux.txt    # Linux 专用依赖
└── pyproject.toml            # 包配置
```

## 开发

### 配置开发环境

```bash
git clone https://github.com/cycleuser/Liao.git
cd Liao
pip install -e ".[all,dev]"
```

### 运行测试

```bash
pytest tests/ -v
```

### 构建与发布

```bash
# 构建包
python -m build

# 上传到 PyPI
twine upload dist/*
```

## 常见问题

### Windows

- **"pywin32 not found"**：运行 `pip install pywin32` 并重启 Python
- **截图失败**：如需截取受保护的窗口，请以管理员身份运行

### Linux

- **"xdotool not found"**：运行 `sudo apt install xdotool` 安装
- **输入模拟不工作**：确保已安装 xdotool，且目标窗口为 X11 或 XWayland 窗口
- **Wayland 截图失败**：安装 GStreamer 和 PipeWire 相关包，出现提示时授予屏幕捕获权限
- **OCR 返回空结果**：安装 OCR 引擎（`pip install rapidocr-onnxruntime` 或 `pip install pytesseract`）

## 许可证

本项目采用 GNU 通用公共许可证 v3.0。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎贡献代码。请在 GitHub 上提交 Issue 和 Pull Request。

## 致谢

- [EasyOCR](https://github.com/JaidedAI/EasyOCR) 和 [RapidOCR](https://github.com/RapidAI/RapidOCR) 提供文字识别
- [PySide6](https://doc.qt.io/qtforpython-6/) 提供 GUI 框架
- [Ollama](https://ollama.ai/) 提供本地 LLM 推理
