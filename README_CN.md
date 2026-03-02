# LLM Chat

基于视觉的GUI界面交互辅助智能体，集成大语言模型。

一个使用视觉/OCR能力和LLM驱动的理解能力来自动化桌面聊天应用的Python包。支持任意OpenAI兼容API（Ollama、OpenAI等），并提供双语GUI界面（中文/英文）。

## 功能特性

- **基于视觉的自动化**: 使用OCR理解GUI元素并自动化交互
- **OpenAI兼容API**: 支持Ollama（本地）、OpenAI及任意OpenAI兼容API
- **双语GUI**: 中英文界面，支持运行时语言切换
- **聊天应用检测**: 自动检测微信、QQ、Telegram等聊天应用
- **区域检测**: 自动和手动的对话/输入区域检测
- **回复门控**: 智能对话流程，等待回复后再发送新消息
- **PyPI就绪**: 可通过pip分发的标准化包

## 安装

### 从PyPI安装（发布后）

```bash
pip install llm-chat
```

### 安装可选依赖

```bash
# 带OCR支持（推荐）
pip install llm-chat[ocr]

# 所有可选依赖
pip install llm-chat[all]
```

### 从源码安装

```bash
git clone https://github.com/cycleuser/llm-chat.git
cd llm-chat
pip install -e ".[all,dev]"
```

## 系统要求

- Python 3.9+
- Windows系统（使用Win32 API）
- OCR需要: EasyOCR、RapidOCR或pytesseract
- LLM需要: 本地运行的Ollama，或任意OpenAI兼容API和API密钥

## 快速开始

### 启动GUI

```bash
llm-chat
# 或
python -m llm_chat
```

### 列出可用窗口

```bash
llm-chat list
llm-chat list --chat-only
```

### 无头自动化

```bash
llm-chat auto --title "微信" --model llama3 --rounds 5
```

### 程序化使用

```python
from llm_chat import VisionAgent, LLMClientFactory
from llm_chat.core import WindowManager

# 创建LLM客户端（Ollama本地）
llm = LLMClientFactory.create_client(
    provider="ollama",
    base_url="http://localhost:11434",
    model="llama3"
)

# 或使用OpenAI兼容API和API密钥
llm = LLMClientFactory.create_client(
    provider="openai",
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4"
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

# 运行自动化
agent.run()
```

## GUI使用

1. **连接LLM**: 输入URL（默认：Ollama localhost:11434）、可选API密钥，点击连接
2. **选择窗口**: 点击刷新，然后双击选择窗口
3. **设置区域**: 点击"截图并检测"或手动选择区域
4. **开始聊天**: 输入提示词并点击"开始自动对话"

## 运行截图

![主窗口（英文）](images/main_window_en.png)

![主窗口（中文）](images/main_window_zh.png)

## 开发

### 设置开发环境

```bash
git clone https://github.com/cycleuser/llm-chat.git
cd llm-chat
pip install -e ".[all,dev]"
```

### 运行测试

```bash
pytest tests/ -v
```

### 生成截图

```bash
python scripts/generate_screenshots.py
```

### 构建并上传到PyPI

```bash
# Windows
publish.bat build    # 仅构建
publish.bat check    # 构建并检查
publish.bat test     # 上传到TestPyPI
publish.bat          # 上传到PyPI

# Linux/macOS
chmod +x publish.sh
./publish.sh build   # 仅构建
./publish.sh check   # 构建并检查
./publish.sh test    # 上传到TestPyPI
./publish.sh         # 上传到PyPI
```

**上传PyPI前提条件:**
1. 在 [PyPI](https://pypi.org) 和/或 [TestPyPI](https://test.pypi.org) 创建账户
2. 从账户设置中生成API令牌
3. 设置令牌为环境变量:
   - Windows: `set TWINE_PASSWORD=pypi-xxxx`
   - Linux/macOS: `export TWINE_PASSWORD=pypi-xxxx`
   - 或创建 `~/.pypirc` 文件保存凭据

## 项目结构

```
llm-chat/
├── src/llm_chat/
│   ├── __init__.py
│   ├── _version.py          # 版本号唯一来源
│   ├── api.py                # 公共API (VisionAgent)
│   ├── cli.py                # CLI入口点
│   ├── core/                 # 核心模块
│   ├── llm/                  # LLM客户端
│   ├── agent/                # 代理工作流
│   ├── gui/                  # PySide6 GUI
│   └── models/               # 数据模型
├── tests/
├── scripts/
├── images/
├── pyproject.toml
└── README.md
```

## 许可证

本项目采用GNU通用公共许可证v3.0 - 详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎贡献！请随时提交Pull Request。

## 致谢

- 使用 [EasyOCR](https://github.com/JaidedAI/EasyOCR) 进行文字识别
- 使用 [PySide6](https://doc.qt.io/qtforpython-6/) 构建GUI
