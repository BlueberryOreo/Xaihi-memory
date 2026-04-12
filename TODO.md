# TODO - 赛希记忆系统优化

## 高优先级

- [ ] **修复 LLM summary 截断问题** (`llm_summarizer.py`)
  - 现象：auto_summary 的 summary 字段偶尔被截断（如以"说的"、"得到"结尾）
  - 原因：LLM 输出的 JSON 中 summary 包含未转义引号，导致 JSON 解析失败，regex fallback 用 `[^"]+` 提取时提前截断
  - 方案：
    1. prompt 中要求 summary 控制在 150 字以内，不包含引号
    2. regex fallback 改用 `"summary"\s*:\s*"` 到 `"topics"` 之间的内容（`re.DOTALL`）
    3. 提取后检查完整性（以动词/助词结尾则标记不完整）
  - 影响的记忆 ID：`mem-c46a40028d15`、`mem-31cefa90d293`

## 中优先级

- [ ] **记忆去重** (`remember_engine.py`)
  - import_memories 和手动导入可能产生重复记忆
  - 需要在 add_memory 前检查向量相似度，相似度 > 0.95 时跳过或更新 *具体策略待重新讨论*

## 低优先级

- [ ] **embedding 缓存**
  - 相同内容重复调用 embedding API 浪费资源
  - 可以加一个简单的 hash->embedding 缓存

- [ ] **记忆衰减机制**
  - 长期未被检索的记忆降低 importance
  - 避免 ChromaDB 无限增长

---
*创建时间：2026-04-12*
*创建者：赛希*

---
*2026-04-13 管理员批注*

> 我看了一下具体的llm_summarizer.py中的正则表达式，同时又看了一下近期总结出问题的内容，我认为被截断的原因是llm在输出的时候，遇到引用的话的时候使用了`""`，从而导致正则表达式提取的时候提前结束了匹配。因此修改了`summarize_conversation.txt`，在里面明确加入了summarize字段中的引号必须使用中文全角引号，不能使用英文引号。如果确实是这个原因，那么这样修改应该可以解决这个问题。

> 当然这个只能解决中文的情况，如果总结是用英文，那还是会出现这个问题。还需要更好的修改方式。
