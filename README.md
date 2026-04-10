# Xaihi-memory

[[中文]](./README_ZH.md)

<div align="center">
    <img src="https://endfield.wiki.gg/images/Snapshot_Xaihi_1.png?9fc2c7" alt="Xaihi" style="width:50%;"/>
    <div>
        <i> This is Xaihi. She's cute. </i>
    </div>
</div>

A personal memory system for Claude Code, designed to maintain long-term conversational context across sessions.

## Overview

Xaihi-memory stores conversation summaries in a vector database (ChromaDB) and retrieves relevant memories based on the current conversation context. It's built to work seamlessly with Claude Code's hook system.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│  UserPrompt     │────>│  Recall Engine   │────>│   ChromaDB    │
│  Submit Hook    │     │  (vector search) │     │  (memories)   │
└─────────────────┘     └──────────────────┘     └───────────────┘
         │
         │ (after each turn)
         ▼
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│    Stop Hook    │────>│ Remember Engine  │────>│   Buffer      │
│                 │     │  (accumulate)    │     │  (jsonl)      │
└─────────────────┘     └──────────────────┘     └───────────────┘
                                                           │
                                                           │ (every 10 rounds)
                                                           ▼
                                                  ┌───────────────┐
                                                  │ LLM Summarizer│
                                                  │  (compress)   │
                                                  └───────────────┘
```

## Features

- **Vector-based memory retrieval**: Uses text-embedding-v4 for semantic search
- **Automatic summarization**: Conversation buffer is summarized and stored every 10 rounds
- **Hook integration**: Works with Claude Code's UserPromptSubmit, Stop, and SessionEnd hooks
- **Coming soon...**

## Project Structure

```
Xaihi-memory/
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
├── src/
│   ├── __init__.py
│   ├── config.py         # Config loader (with .bashrc fallback)
│   ├── chroma_client.py  # ChromaDB operations
│   ├── embedding.py      # Embedding client (text-embedding-v4)
│   ├── llm_summarizer.py # LLM-based conversation summarizer
│   ├── recall_engine.py  # Memory retrieval engine
│   └── remember_engine.py# Memory accumulation engine
├── prompts/
│   └── README.md        # Prompt templates (write your own)
├── stop_hook.sh          # Claude Code Stop hook script
├── session_end_hook.sh   # Claude Code SessionEnd hook script
└── recall.sh             # CLI for testing recall
```

## Reference Project

- [LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) - An intelligent long-term memory plugin for AstrBot with hybrid retrieval and automatic summarization

## TODO

- [ ] Automatic forgetting strategy
- [ ] Importance decay mechanism

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `config.yaml` directly, or add to `~/.bashrc`:

```bash
export DASHSCOPE_API_KEY="your-key"
export DASHSCOPE_BASE_URL="your-base-url"
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="your-base-url"
```

Config loading priority:
1. Values in `config.yaml`
2. Environment variables from `~/.bashrc`

### 3. Configure Claude Code Hooks

Add to `~/.claude/settings.json` (see [Hooks Documentation](https://code.claude.com/docs/en/hooks)):

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/memory/session_end_hook.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/memory/stop_hook.sh"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/memory/recall.sh"
          }
        ]
      }
    ]
  }
}
```

## Configuration

Key settings in `config.yaml`:

| Section | Key | Description | Default |
|---------|-----|-------------|---------|
| `memory` | `top_k` | Number of memories to retrieve | 5 |
| `memory` | `summary_trigger_rounds` | Rounds before auto-summarize | 10 |
| `recall` | `max_context_length` | Max characters in recall output | 2000 |
| `chroma` | `persist_dir` | ChromaDB storage path | `~/.claude/memory/chroma_db` |

## Usage

### Manual Memory Recall

```bash
cd ~/agent/memory
python -m src.recall_engine "your query here"
```

### Import Existing Memories

```bash
cd ~/agent/memory
python import_memories.py
```

### View Stored Memories

```bash
cd ~/agent/memory
python list_memory.py
```

## API Configuration (You can replace these with your own API)

### Embedding
- **Model**: text-embedding-v4
- **Dimension**: 1024
- **Endpoint**: Configurable via `embedding.base_url`

### LLM (for summarization)
- **Model**: qwen3.5
- **Temperature**: 0.3
- **Timeout**: 120s

## Privacy

Sensitive conversation files can be excluded from the vector database. Use the `exclude_paths` setting in `config.yaml` to add files or directories you want to keep private.

## License

MIT

## Acknowledgement

This repository is fully developed by **Xaihi**, powered by **MiniMax-M2.7** and built with **Claude Code**. We extend our gratitude to the [LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) project for its invaluable inspiration and codebase reference. Special thanks to **@qq1244** from the **Linux.do** community for providing the model API. 
