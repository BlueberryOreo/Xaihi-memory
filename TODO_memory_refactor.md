# Memory System Refactor TODO

> Created: 2026-05-18 16:58
> Status: In Progress

## 核心设计

### 回忆分数公式

```
recall_score(Q, m) = w1 × cos(E_Q, E_m) + w2 × effective_importance(m)
```

- `cos(E_Q, E_m)`：向量余弦相似度，范围 [0, 1]
- `effective_importance(m)`：当前重要性，范围 [0, 1]
- `w1, w2` 配置在 config.yaml，w1 + w2 = 1

### 检索流程

```
Step 1: 向量检索（ChromaDB）
  Q → E_Q
  ChromaDB 返回 top_k 条，按 cos 降序排列

Step 2: 相似度下限过滤
  if max(cos) < T_min → 全部丢弃，返回空
  否则继续

Step 3: 内存重排序
  对 top_k 条记忆计算 recall_score
  按 recall_score 降序排列

Step 4: 只更新通过过滤的记忆
  access_count += 1
  effective = calc_effective_importance(...)
  写入 importance
```

### 参数设计

```yaml
recall:
  top_k: 5              # 最终返回的记忆数量
  top_candidates: 20    # 向量检索候选窗口
  min_similarity: 0.60  # 最低向量相似度阈值
  weight_similarity: 0.6  # w1: 相似度权重
  weight_importance: 0.4  # w2: 重要性权重
```

### 动态阈值（可选）

```
query_density = len(semantic_words) / len(all_words)
T_min = min_sim + (1 - query_density) × margin
```
短查询阈值更高，长查询阈值较低。

## 1. 4月记忆 base_importance 重置

- 当前：180条 4月记忆 base_importance = 0.5
- 目标：重置为 0.75
- 原因：避免沉降到 min_importance 以下后被永久过滤

## 2. 去掉 min_importance 过滤

- 当前：`chroma_client.search()` 用 `where={"importance": {"$gte": 0.3}}`
- 问题：一刀切过滤，导致重要性低的记忆完全无法被召回
- 目标：去掉过滤，改为综合排序

## 3. 综合"回忆分数"排序

- 当前：纯按向量余弦相似度排序
- 目标：`score = w1 * cos + w2 * importance`
- 权重放在 config.yaml 中

## 4. 相似度下限过滤

- 当前：无下限，任何相似度都能返回结果
- 目标：max(cos) < T_min 时不注入、不更新任何计数

## 5. 只有成功注入才更新 access_count

- 当前：recall 时无条件更新所有 top_k 记忆的 access_count
- 目标：只更新通过过滤的记忆

## 6. recall 时实时更新 importance

- 当前：recall 时不更新 importance，只在 decay_all() 时更新
- 目标：recall 成功注入时同时计算并写入新的 effective importance

## 7. SessionStart/SessionEnd 简化

- 当前：decay_all() 全量遍历更新所有记忆 importance
- 目标：只做沉降判断，不再全量更新

## 测试计划

- [ ] 随机问候查询（如"嗨赛希在吗"）→ 应无记忆注入
- [ ] 半相关查询（如"扩散模型加速"）→ 应召回相关记忆
- [ ] 完全相关查询（如"记忆系统 v2 沉降机制"）→ 应召回高相关记忆
- [ ] 验证不同查询下的 recall_score 分布

## 待办：优化 embedding 输入

### 问题描述

- text-embedding-v4 (1024 维) 对长文本（记忆通常 200-500 字）的区分度不够
- cosine 分布在 0.5-0.7 之间扎堆，好坏记忆挤在一起
- 记忆内容包含大量修辞性语言（"在知识的荒原上点亮新的火把"），对向量检索无帮助
- 导致 recall_score 中 importance 的权重（0.4）几乎主导排序，cosine 分化能力弱

### 方案 1：缩短输入文本再 embedding

#### 查询侧优化

- 用 LLM 提取 query 的核心意图/关键词，而不是直接用原始查询文本
- 示例：`"扩散模型加速"` → `"视频扩散模型推理加速方法 cache 预测"`

#### 记忆侧优化

- 存储时生成两份文本：
  - `content`：完整摘要（用于输出）
  - `embedding_text`：精炼版（用于 embedding，100-150 字）
- 精炼策略：
  - 优先使用 `topics` 和 `key_facts`（已经是结构化数据）
  - 如果 key_facts 不足，从 content 提取关键短语
  - 去掉修辞性/情感性语言
- 示例：
  - 原始：`"管理员将明日的研究计划托付于我，这仿佛是在知识的荒原上点亮新的火把..."`
  - embedding_text: `"研究计划 视频扩散模型 推理加速 调研基于 cache 的视频扩散模型推理加速方法 确认是否存在 attention-guided step skipping 的研究 gap 重点关注 TeaCache、TaylorSeer 等论文"`

#### 实施步骤

1. **修改 `summarize_and_store()`**：
   - 从 LLM 输出中提取 topics 和 key_facts
   - 生成 embedding_text = ' '.join(topics) + ' ' + ' '.join(key_facts[:5])
   - 截断到 150 字符
   - 存储时同时保存 content 和 embedding_text

2. **修改 `chroma_client.add_memory()`**：
   - 新增 `embedding_text` 字段（可选）
   - 如果有 embedding_text，用 embedding_text 生成 embedding
   - 否则 fallback 到 content

3. **修改 `recall_engine.py`**：
   - 查询时也生成 query 的 embedding_text（用 query 本身 + 提取的关键词）

4. **迁移旧记忆**：
   - 批量读取所有记忆
   - 生成 embedding_text = ' '.join(topics) + ' ' + ' '.join(key_facts[:5])
   - 用新 embedding_text 重新 embedding
   - 更新 chroma 中的 embedding

5. **测试验证**：
   - 对比新旧方案的 cosine 分布
   - 验证召回质量和过滤效果
  - 原始：`"管理员将明日的研究计划托付于我，这仿佛是在知识的荒原上点亮新的火把。我们要调研基于 cache 的视频扩散模型推理加速方法，特别是确认是否有人做过 attention-guided step skip..."`
  - 缩短：`"2026-05-xx 管理员委托调研 cache-based 视频扩散模型推理加速方法，关注 attention-guided step skipping 是否有人做过。计划验证 VS Code Claude Code 插件的 CLI 架构。"`

### 方案 2：替换为本地检索模型

#### 候选模型

- **bge-m3**：多语言、多粒度、支持检索优化
- **gte**：Alibaba 的检索专用模型
- **e5**：Microsoft 的嵌入模型，检索效果好
- **mxbai-embed**：混合检索，支持中英文

#### 实施步骤

1. 本地部署候选模型，测试 embedding 质量
2. 对比 text-embedding-v4 的 cosine 分布
3. 选择效果最好的模型
4. 用新模型重新 embedding 所有记忆
5. 更新 embedding.py 支持本地模型

### 方案 3：调整权重

- 如果 cosine 区分度低，降低 w_similarity、提高 w_importance
- 例如：`w1=0.3, w2=0.7`
- 作为临时方案，在方案 1/2 实施前使用

## 需要修改的文件

1. `recall_engine.py` — recall 逻辑重写
2. `chroma_client.py` — search 方法去掉过滤
3. `remember_engine.py` — 简化 decay_all()
4. `config.yaml` — 新增排序权重、相似度下限等参数
5. 数据重置脚本 — 4 月记忆 base_importance 更新
6. `embedding.py` — 支持缩短输入和/或本地模型
7. `summarizer.py` — 生成 embedding_text（精炼版）
