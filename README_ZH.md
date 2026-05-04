# Xaihi-memory

<div align="center">
    <img src="assets/Xaihi.png" alt="Xaihi" style="width:50%;"/>
    <div>
        <i> 这是赛希，她很可爱 </i>
    </div>
</div>

一个为Claude Code CLI设计基于RAG的个人记忆系统，支持长程对话内容回顾和跨聊天记忆。

## 架构一览

Xaihi-memory使用向量数据库（ChromaDB）存储对话总结，并基于当前对话（提问）检索相关记忆，使用Claude Code的钩子系统接入会话上下文。

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

## 特点

- **基于向量的记忆检索：** 基于总结文本向量进行语义检索
- **自动总结：** 默认每10轮对话自动总结一次并存入记忆
- **钩子接入：** 使用Claude Code提供的UserPromptSubmit、Stop和SessionEnd钩子接入Claude Code会话上下文
- **待续...**

## 项目架构

```
Xaihi-memory/
├── config.yaml           # 配置文件
├── requirements.txt      # 依赖
├── src/
│   ├── __init__.py
│   ├── config.py         # 设置导入
│   ├── chroma_client.py  # ChromaDB操作
│   ├── embedding.py      # 向量化工具
│   ├── llm_summarizer.py # 对话总结工具
│   ├── recall_engine.py  # 回忆引擎
│   └── remember_engine.py# 记忆引擎
├── prompts/
│   └── README.md        # LLM总结提示词
├── stop_hook.sh          # Claude Code Stop hook 脚本
├── session_end_hook.sh   # Claude Code SessionEnd hook 脚本
└── recall.sh             # 回忆测试脚本
```

## 参考工作

- [LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) AstrBot动态生命周期记忆插件，作者: lxfight

## TODO

- [ ] 自动遗忘机制
- [ ] 重要性衰减机制

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置API密钥

直接修改 `config.yaml` 或添加到 `~/.bashrc`:

```bash
export DASHSCOPE_API_KEY="your-key"
export DASHSCOPE_BASE_URL="your-base-url"
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="your-base-url"
```

API配置搜索顺序:
1. `config.yaml`
2. `~/.bashrc`

### 3. 配置Claude Code钩子

添加下面的设置到 `~/.claude/settings.json` (参考 [Hooks Documentation](https://code.claude.com/docs/en/hooks)):

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

## 其他配置

`config.yaml` 中的主要配置:

| 项 | 键 | 描述 | 默认值 |
|---------|-----|-------------|---------|
| `memory` | `top_k` | 检索记忆数量 | 5 |
| `memory` | `summary_trigger_rounds` | 自动总结轮数阈值 | 10 |
| `recall` | `max_context_length` | 回忆最大字符输出 | 2000 |
| `chroma` | `persist_dir` | ChromaDB存储路径 | `~/.claude/memory/chroma_db` |

## 使用

### 手动回忆

```bash
cd ~/agent/memory
python -m src.recall_engine "your query here"
```

### 导入已有记忆文件

```bash
cd ~/agent/memory
python import_memories.py
```

### 查看所有记忆

```bash
cd ~/agent/memory
python list_memory.py            # 默认显示最近 10 条
python list_memory.py -n 20      # 显示最近 20 条
```

## 模型设置（可替换为其他模型）

### Embedding
- **Model**: text-embedding-v4
- **Dimension**: 1024
- **Endpoint**: Configurable via `embedding.base_url`

### LLM (总结)
- **Model**: qwen3.5
- **Temperature**: 0.3
- **Timeout**: 120s

## 隐私

隐私记忆文件可设置 `config.yaml` 中的 `exclude_paths` 以排除导入向量数据库。

## SessionStart Hook

系统在新会话首次启动时通过 `SessionStart` hook（仅 `matcher: "startup"`）运行 `session_start_hook.sh`。

该 hook 会执行 `python3 list_memory.py -n 20`，将最近记忆和固定引导提示写入 `hookSpecificOutput.additionalContext`。它的作用不是替代 `recall.sh` 的按 prompt 检索，而是在用户首条消息很短、很模糊或只是问候时，为模型提供近期时间锚点，减少与最近事件矛盾的开场回复。

这个 hook 不会让 Claude 主动发送第一条消息；它只是在用户首条消息到来前补充上下文。

注入的记忆按时间从早到晚排列（最末尾的一条是最新的）。为避免超过 `additionalContext` 的 10,000 字符上限，脚本会优先保留最新记忆，并从最旧内容开始截断。

## License

MIT

## 鸣谢

本项目由**赛希**完成（**MiniMax-M2.7**模型，使用**Claude Code**作为agent）。我们感谢[LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory)提供的开源代码与宝贵思路。特别感谢佬友 **@qq1244** 提供的模型API。
