# Liao 知识库集成说明

## 概述

Liao 现已支持**可选的知识库（KB）功能**，完全**兼容 GangDan 的 ChromaDB 格式**。这意味着：

- ✅ Liao 可以直接读取 GangDan 的知识库，无需数据复制
- ✅ 支持严格知识库模式（无检索结果时拒绝回答）
- ✅ 支持跨多个知识库搜索和综述
- ✅ 支持跨语言检索（如中文提问 → 英文文档）

## 与 GangDan 的兼容性

### 直接使用 GangDan 知识库

Liao 的知识库模块设计为**直接读取 GangDan 的 ChromaDB 导出格式**：

```python
from liao.knowledge import KBConfig

config = KBConfig(
    chroma_dir="/home/fred/GangDan/data/chroma",  # 指向 GangDan 的 KB
   embedding_model="nomic-embed-text",
   ollama_url="http://localhost:11434",
)
```

### 共享用户创建的知识库

两个项目可以共享同一个 ChromaDB 目录，或者通过配置文件同步：

```bash
# 方案 1: 直接共享
cp -r ~/GangDan/data/chroma ~/.liao/kb/chroma

# 方案 2: 配置文件指向同一位置
# ~/.liao/kb/config.json
{
  "chroma_dir": "/home/fred/GangDan/data/chroma"
}
```

## 快速开始

### 1. 安装依赖

```bash
cd Liao
pip install chromadb requests
```

### 2. 基础使用示例

```python
from liao import VisionAgent
from liao.knowledge import KBConfig
from liao.llm.factory import LLMClientFactory
from liao.core.window_manager import WindowManager

# 配置知识库
kb_config = KBConfig(
    chroma_dir="/home/fred/GangDan/data/chroma",
   embedding_model="nomic-embed-text",
   ollama_url="http://localhost:11434",
   strict_kb_mode=False,  # 非严格模式
)

# 创建 LLM 客户端
llm = LLMClientFactory.create_client(provider="ollama", model="llama3")

# 查找目标窗口
wm = WindowManager()
window = wm.find_window_by_title("WeChat")

# 创建启用 KB 的 agent
agent = VisionAgent(
   llm_client=llm,
   target_window=window,
   prompt="你是一个有帮助的编程助手。",
   max_rounds=10,
   use_kb=True,           # 启用知识库
   kb_config=kb_config,   # KB 配置
)

# 运行自动化
agent.run()
```

### 3. 严格模式

在严格模式下，当知识库中没有相关内容时，Liao 会拒绝回答：

```python
kb_config = KBConfig(
   strict_kb_mode=True,  # 启用严格模式
)
```

这确保了回答的准确性，避免 AI"胡编乱造"。

### 4. 多知识库综述

可以指定搜索特定的知识库集合：

```python
from liao.knowledge import KBManager

manager = KBManager(kb_config)

# 搜索特定 KB
context, sources = manager.search_and_synthesize(
    "如何使用 DataFrame？",
   collections=["pandas", "numpy"],  # 限制搜索范围
   max_chars=6000
)

print(f"参考来源：{sources}")
```

## 核心功能

### 1. 知识库检索

- **向量相似度搜索**：使用 ChromaDB 进行高效的向量检索
- **距离阈值过滤**：只返回相关度高的结果（distance < 0.5）
- **Top-K 限制**：默认返回最相关的 10 条结果

### 2. 跨语言支持

- 自动检测查询语言
- 在多种语言的文档中搜索
- 支持中英文混合检索

### 3. 严格模式

```python
if kb_manager.is_strict_mode():
   print("严格模式：无 KB 结果时拒绝回答")
```

### 4. 知识库管理

```python
# 列出所有 KB
kbs = manager.list_kbs()

# 设置搜索范围
manager.set_kb_scope(["numpy", "pandas"])

# 清除范围（搜索所有）
manager.clear_kb_scope()

# 切换严格模式
manager.set_strict_mode(True)
```

## 架构设计

```
┌─────────────────────────────────────┐
│         Liao Agent                  │
├─────────────────────────────────────┤
│  AgentWorkflow                      │
│  ├─ ConversationMemory              │
│  └─ KBManager (可选)                │
│      ├─ KBRetriever                 │
│      │   └─ ChromaDB Client         │
│      └─ KBConfig                    │
└─────────────────────────────────────┘
                ↓
    ┌───────────────────────┐
    │   ChromaDB 目录        │
    │  (GangDan 兼容格式)    │
    │  - chroma/            │
    │    - collection_uuid/ │
    │      - *.sqlite       │
    │      - *.bin          │
    └───────────────────────┘
```

## 从 GangDan 迁移

### 选项 A：直接共享（推荐）

```python
config = KBConfig(chroma_dir="/home/fred/GangDan/data/chroma")
```

### 选项 B：复制数据

```bash
cp -r ~/GangDan/data/chroma ~/.liao/kb/chroma
cp ~/GangDan/data/user_kbs.json ~/.liao/kb/
```

### 选项 C：导出/导入（未来功能）

```bash
gangdan kb export my-kb --output /tmp/my-kb.zip
liao kb import/tmp/my-kb.zip
```

## 测试

### 测试 1：验证 ChromaDB 连接

```python
from liao.knowledge import KBConfig, KBManager

config = KBConfig(chroma_dir="/home/fred/GangDan/data/chroma")
manager= KBManager(config)

print(f"ChromaDB 可用：{manager.retriever.is_available()}")
print(f"知识库列表：{manager.list_kbs()}")
```

### 测试 2：测试搜索

```python
context, sources = manager.search_and_synthesize("NumPy 数组")
print(f"上下文长度：{len(context)}")
print(f"来源：{sources}")
```

### 测试 3：测试严格模式

```python
manager.set_strict_mode(True)
response = manager.search_and_synthesize("不存在的话题 xyz123")
print(response)  # 应返回空或错误消息
```

## 运行演示

```bash
cd Liao
python examples/kb_demo.py
```

这会展示：
- 可用的知识库列表
- 搜索功能演示
- 严格模式演示
- 多知识库综述演示

## 故障排除

### ChromaDB 未找到

```
错误：ChromaDB directory not found: /path/to/chroma
```

**解决方案**：确保路径指向有效的 ChromaDB 目录（包含 UUID 命名的子目录）。

### 无法生成嵌入

```
错误：Failed to generate query embedding
```

**解决方案**：
1. 检查 Ollama 是否运行：`ollama list`
2. 验证嵌入模型存在：`ollama pull nomic-embed-text`
3. 检查配置中的 `ollama_url`

### 严格模式过于严格

如果严格模式阻止了有用的回答：

```python
config.strict_kb_mode = False
kb_manager.set_strict_mode(False)
```

## 与 GangDan 的对比

| 功能 | GangDan | Liao (新增) |
|------|---------|------------|
| 向量数据库 | ChromaDB/FAISS/内存 | 仅 ChromaDB |
| 格式 | 私有 | 与 GangDan 兼容 |
| 严格模式 | ✅ 是 | ✅ 是 |
| 多 KB 搜索 | ✅ 是 | ✅ 是 |
| 跨语言 | ✅ 是 | ✅ 基础支持 |
| 网络搜索 | ✅ 是 | ❌ 暂无 |
| 文档上传 | ✅ 是 | ❌ 暂无 |
| 学习模块 | ✅ 是 | ❌ 不计划 |
| GUI 聊天 | ✅ 是 | ❌ 不计划 |
| 桌面自动化 | ❌ 否 | ✅ 核心功能 |

## 未来计划

- [ ] 完整的跨语言翻译（如 GangDan）
- [ ] 网络搜索集成
- [ ] 文档上传/导入 UI
- [ ] KB 可视化和管理 GUI
- [ ] 基于对话上下文的自动 KB 建议

## 文件结构

```
Liao/
├── src/liao/knowledge/
│   ├── __init__.py            # 包导出
│   ├── kb_config.py           # 配置管理
│   ├── kb_manager.py          # 高级 KB 接口
│   └── retriever.py           # ChromaDB 检索
├── examples/
│   └── kb_demo.py             # 演示脚本
├── KB_INTEGRATION.md            # 英文集成指南
├── KB_IMPLEMENTATION_SUMMARY.md # 实现总结
└── README_KB_ZH.md              # 本文件
```

## 总结

Liao 的知识库模块提供了：

1. ✅ **GangDan 兼容性** - 直接读取现有 KB，无需数据 duplication
2. ✅ **简洁架构** - 关注点分离，易于维护
3. ✅ **可选功能** - 不影响非 KB 使用场景
4. ✅ **可扩展设计** - 易于添加新功能
5. ✅ **严格模式** - 确保回答准确性
6. ✅ **多 KB 综述** - 跨知识库汇总信息

详细的集成步骤请参考：
- 英文文档：[KB_INTEGRATION.md](KB_INTEGRATION.md)
- 实现细节：[KB_IMPLEMENTATION_SUMMARY.md](KB_IMPLEMENTATION_SUMMARY.md)
