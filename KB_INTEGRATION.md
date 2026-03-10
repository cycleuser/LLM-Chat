# Liao Knowledge Base Integration Guide

## Overview

Liao now supports optional knowledge base (KB) integration that is **compatible with GangDan's ChromaDB format**. This allows Liao to:

- Access existing GangDan knowledge bases without duplication
- Support strict KB mode (refuse to answer when no relevant content found)
- Search across multiple KBs and synthesize results
- Perform cross-lingual retrieval (e.g., Chinese query → English docs)

## Compatibility with GangDan

Liao's KB module reads ChromaDB databases in the **same format as GangDan**, allowing you to:

1. Point Liao to GangDan's ChromaDB directory: `~/GangDan/data/chroma/`
2. Use the same embedding models (via Ollama)
3. Share user-created knowledge bases between projects

## Setup

### 1. Install Dependencies

```bash
cd Liao
pip install chromadb requests
```

### 2. Configure KB

Create or edit `~/.liao/kb/config.json`:

```json
{
  "embedding_model": "nomic-embed-text",
  "chroma_dir": "/home/fred/GangDan/data/chroma",  // Use GangDan's KB
  "ollama_url": "http://localhost:11434",
  "strict_kb_mode": false,
  "top_k": 10
}
```

Or use Liao's default location: `~/.liao/kb/chroma/`

### 3. Programmatic Usage

#### Basic Example

```python
from liao import VisionAgent
from liao.knowledge import KBConfig, KBManager
from liao.llm.factory import LLMClientFactory

# Configure KB
config = KBConfig(
    chroma_dir="/path/to/gangdan/data/chroma",  # Or ~/.liao/kb/chroma
    embedding_model="nomic-embed-text",
    ollama_url="http://localhost:11434",
   strict_kb_mode=False,  # Refuse to answer without KB results
)

# Create KB manager
kb_manager = KBManager(config)

# List available KBs
kbs = kb_manager.list_kbs()
print(f"Available KBs: {[kb['name'] for kb in kbs]}")

# Test search
context, sources = kb_manager.search_and_synthesize("NumPy array operations")
print(f"Context from sources: {sources}")
```

#### Integration with VisionAgent

```python
from liao import VisionAgent
from liao.knowledge import KBConfig
from liao.llm.factory import LLMClientFactory
from liao.core.window_manager import WindowManager

# Setup KB config
kb_config = KBConfig(
    chroma_dir="/path/to/gangdan/data/chroma",
    embedding_model="nomic-embed-text",
   strict_kb_mode=True,  # Only answer with KB support
   kb_scope=["numpy", "pandas"],  # Limit to specific KBs
)

# Create LLM client
llm = LLMClientFactory.create_client(provider="ollama", model="llama3")

# Find target window
wm = WindowManager()
window = wm.find_window_by_title("WeChat")

# Create agent with KB support
agent = VisionAgent(
   llm_client=llm,
   target_window=window,
   prompt="You are a helpful programming assistant. Use the knowledge base to provide accurate answers.",
   max_rounds=10,
   use_kb=True,  # Enable KB
   kb_config=kb_config,
)

# Run automation
agent.run()

# Access conversation history
for msg in agent.conversation.messages:
   print(f"{msg.sender}: {msg.content}")
```

### 4. CLI Usage (Coming Soon)

```bash
# List available KBs
liao kb list

# Search KB
liao kb search "NumPy arrays" --kb numpy scipy

# Enable strict mode
liao kb config set strict_mode true

# Point to GangDan's KB
liao kb config set chroma_dir ~/GangDan/data/chroma
```

## Features

### Strict KB Mode

When `strict_kb_mode=True`, Liao will refuse to answer questions if no relevant KB content is found:

```python
config = KBConfig(strict_kb_mode=True)
kb_manager = KBManager(config)

if kb_manager.is_strict_mode():
   print("Will only answer with KB support")
```

### Multi-KB Synthesis

Search across multiple knowledge bases and synthesize results:

```python
# Search specific KBs
context, sources = kb_manager.search_and_synthesize(
    "How to use DataFrame?",
   collections=["pandas", "numpy"],
   max_chars=6000
)

print(f"Synthesized from: {sources}")
# Output: Synthesized from: ['pandas_df_guide.md', 'numpy_arrays.md']
```

### KB Scope Limitation

Limit searches to specific KBs:

```python
# Set scope
kb_manager.set_kb_scope(["pytorch", "tensorflow"])

# Clear scope (search all)
kb_manager.clear_kb_scope()
```

## Architecture

```
┌─────────────────────────────────────────┐
│            Liao Agent                   │
├─────────────────────────────────────────┤
│  AgentWorkflow                          │
│  ├─ ConversationMemory                  │
│  └─ KBManager (optional)                │
│      ├─ KBRetriever                     │
│      │   └─ ChromaDB Client             │
│      └─ KBConfig                        │
└─────────────────────────────────────────┘
                    ↓
        ┌───────────────────────┐
        │   ChromaDB Directory  │
        │  (GangDan compatible) │
        │  - chroma/            │
        │    - collection_uuid/ │
        │      - *.sqlite       │
        │      - *.bin          │
        └───────────────────────┘
```

## Migration from GangDan

To migrate your GangDan knowledge bases to Liao:

1. **Option A: Direct Sharing** (Recommended)
   ```python
  config = KBConfig(chroma_dir="/home/fred/GangDan/data/chroma")
   ```

2. **Option B: Copy Data**
   ```bash
   cp -r ~/GangDan/data/chroma ~/.liao/kb/chroma
   cp ~/GangDan/data/user_kbs.json ~/.liao/kb/
   ```

3. **Option C: Export/Import** (Future)
   ```bash
   gangdan kb export my-kb --output /tmp/my-kb.zip
   liao kb import /tmp/my-kb.zip
   ```

## Troubleshooting

### ChromaDB Not Found

```
Error: ChromaDB directory not found: /path/to/chroma
```

**Solution**: Ensure the path points to a valid ChromaDB directory with UUID-named subdirectories.

### No Embedding Model

```
Error: Failed to generate query embedding
```

**Solution**: 
1. Check Ollama is running: `ollama list`
2. Verify embedding model exists: `ollama pull nomic-embed-text`
3. Check `ollama_url` in config

### Strict Mode Too Restrictive

If strict mode prevents useful answers:

```python
config.strict_kb_mode = False
kb_manager.set_strict_mode(False)
```

## Future Enhancements

- [ ] Cross-lingual translation (like GangDan)
- [ ] Web search integration
- [ ] Document upload/import UI
- [ ] KB visualization and management GUI
- [ ] Automatic KB suggestions based on conversation context
