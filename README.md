# 客服智能体 (smart-service Agent)

基于 **LLM + RAG + ReAct Agent** 的智能客服系统。支持意图识别、产品检索、价格查询、礼品推荐，作为独立 Widget 嵌入任意网页。

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户 (浏览器)                               │
│                    嵌入式 Chat Widget (Vue 3)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket (Socket.IO)
                             ▼
┌──────────────────────────── Backend (FastAPI + ASGI) ───────────────┐
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    AgentOrchestrator                          │   │
│  │                                                               │   │
│  │   用户消息 ──► IntentClassifier (规则优先)                     │   │
│  │                    │                                          │   │
│  │         ┌──────────┼──────────┐                              │   │
│  │         ▼          ▼          ▼                              │   │
│  │    快速通道     Quick       Full                             │   │
│  │    (模板)      React       React                              │   │
│  │    0 LLM     1 LLM +     ≤3 LLM                              │   │
│  │              PreSearch   调用工具                             │   │
│  │                    │         │                                │   │
│  │                    ▼         ▼                                │   │
│  │              ReactEngine (ReAct 推理)                         │   │
│  │                    │                                          │   │
│  │                    ▼                                          │   │
│  │           ResponseGenerator (回复生成)                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  Redis   │  │PostgreSQL│  │ Zilliz Cloud  │  │ OpenAI-compat │   │
│  │  会话记忆 │  │ 产品·用户 │  │   向量检索     │  │    LLM 接口   │   │
│  └──────────┘  └──────────┘  └──────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent 智能体系统详解

系统采用 **三路路由** 的编排策略，根据用户意图自动选择最优推理路径。

### 2.1 意图分类器 (IntentClassifier)

`backend/app/agent/intent_classifier.py`

**策略：规则优先，LLM 兜底**

1. 遍历 `config/agent_rules.yaml` 中的关键词规则，自上而下匹配
2. 命中则返回对应意图；无匹配则返回 `other`
3. `other` 意图进入完整 ReAct 路径，由 LLM 自行分析

支持的意图类型：

| 意图标识 | 中文含义 | 路由 |
|---------|---------|------|
| `greeting` | 问候语 | 快速通道（模板） |
| `thanks` | 感谢 | 快速通道（模板） |
| `farewell` | 道别 | 快速通道（模板） |
| `capability` | 能力询问 | 快速通道（模板） |
| `product_inquiry` | 产品咨询 | **Quick React** |
| `price_inquiry` | 价格询问 | **Quick React** |
| `spec_inquiry` | 规格询问 | **Quick React** |
| `recommendation` | 送礼推荐 | **Quick React** |
| `purchase_intent` | 购买意向 | **Quick React** |
| `complaint` | 投诉 | 完整 React |
| `other` | 其他 | 完整 React |

### 2.2 主编排器 (AgentOrchestrator)

`backend/app/agent/orchestrator.py`

处理流程：

```
1. 用户识别 (UUID → DB User)
2. 意图分类
3. 长期记忆检索 (并行)
4. ┌─ 快速通道意图 ──► 模板回复，跳过 LLM
   ├─ 产品相关意图 ──► 预搜索 (并行) → Quick React
   └─ 其他意图 ──────► Full React (LLM 自主推理)
5. 响应生成
6. 长期记忆保存 (购买/价格/推荐意图)
```

关键特点：
- **长期记忆与预搜索并行执行**，减少延迟
- **预搜索使用原始用户消息作为查询**，确保召回质量
- 购买类意图自动触发联系人收集

### 2.3 ReAct 推理引擎 (ReactEngine)

`backend/app/agent/react_engine.py`

引擎支持两种运行模式：

#### Quick 模式 (`run_quick`)

```text
预搜索结果 (limit=5) → System Prompt → 1× LLM Call → 最终回复 + 产品卡片
```

- **1 次 LLM 调用**，响应快
- LLM 直接基于预搜索的产品数据组织回复文案
- LLM 不调用工具，不进行 Thought-Action-Observation 循环
- System Prompt 要求必须使用产品数据中的**完整名称**，便于系统匹配产品卡片

#### 完整模式 (`run`)

```text
用户消息 → Thought → Action (调用工具) → Observation → Thought → ... → Final Answer
```

- **最多 3 轮迭代**
- LLM 自主决定何时、如何调用 `product_search` 工具
- 支持 Thought → Action → Observation 标准 ReAct 循环
- `product_search` 由 LLM 自行决定查询参数（可能产生非最优查询）

| 维度 | Quick 模式 | 完整模式 |
|------|-----------|---------|
| LLM 调用次数 | 1 | 1~3 |
| 搜索控制 | 系统自动（用户原始消息） | LLM 自主决策 |
| 适用场景 | 已知产品类意图 | 复杂/未分类意图 |
| 响应延迟 | ~2s | ~4-6s |

#### 产品提取 (`_extract_products`)

引擎从 LLM 回复文本中提取产品名称，与搜索结果匹配，生成前端产品卡片：
1. 在 `final_answer` 文本中按完整名称、核心名称、价格等信息匹配产品
2. 已匹配的产品按出现顺序排列
3. 搜索结果中未被提及的产品追加到末尾

### 2.4 RAG 检索管线

`backend/app/rag/`

```
用户查询 → Embedder → Zilliz Cloud 向量检索 → PostgreSQL 获取详情 → Reranker 重排 → Top-K 结果
```

#### Embedder (`embedder.py`)
- 基于 OpenAI 兼容接口
- 默认模型：`Qwen3-Embedding-4B` (ModelScope)，维度 2560
- 通过 `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` 配置

#### 向量检索 (`retriever.py`)
- 使用 Zilliz Cloud (Milvus 托管)，COSINE 相似度
- 扩大召回范围 (`recall_limit = top_k × 4`)，为重排层提供更多候选
- 支持按分类前缀过滤 (`category like "xxx%"`)
- 检索后从 PostgreSQL 获取完整产品详情

#### 重排序 (`reranker.py`)
基于业务规则的多维度综合排序：

| 维度 | 权重逻辑 |
|------|---------|
| 上下架 | `is_online=0` → -100 分 |
| 热门度 | `is_hot=1` → +5~10 分 |
| 信息完整度 | 有图 +3、有描述 +2 |
| 时效性 | 30 天内线性衰减，上限 5~10 分 |
| 语义相关性 | 向量检索分数 × 2 |
| 价格意图 | 低价意图：得分 ∝ 1/价格；高价意图：得分 ∝ 价格 |

### 2.5 记忆系统

#### 短期记忆 (ShortTermMemory)
`backend/app/memory/short_term.py`

- **存储**：Redis（兜底：内存字典）
- **内容**：对话历史、当前意图、已收集的用户信息
- **TTL**：2 小时
- **用途**：维持多轮对话上下文

#### 长期记忆 (LongTermMemory)
`backend/app/memory/long_term.py`

- **存储**：PostgreSQL `user_memories` 表
- **触发**：购买意向、推荐请求、价格询问
- **检索**：并行执行，按 `relevance_score` 降序 + 时间降序

### 2.6 响应生成器 (ResponseGenerator)

`backend/app/agent/response_generator.py`

三级兜底策略：
1. **LLM 优先**：使用 ReAct 引擎生成的 `final_answer`
2. **搜索兜底**：若 LLM 未生成回复但有产品数据，列出前 3 个产品
3. **模板兜底**：使用 `agent_rules.yaml` 中的模板回复

---

## 3. 项目结构

```
smart-service-agent/
├── backend/                          # Python 后端
│   ├── app/
│   │   ├── agent/                    # Agent 核心
│   │   │   ├── intent_classifier.py  #   意图分类（规则 + LLM）
│   │   │   ├── orchestrator.py       #   主编排器（路由 + 并行协调）
│   │   │   ├── react_engine.py       #   ReAct 推理引擎
│   │   │   └── response_generator.py #   回复生成（三级兜底）
│   │   ├── api/                      # 接口层
│   │   │   ├── chat.py               #   REST 聊天接口
│   │   │   ├── health.py             #   健康检查
│   │   │   ├── products.py           #   产品数据 API
│   │   │   └── websocket.py          #   WebSocket 消息处理
│   │   ├── config/
│   │   │   ├── settings.py           #   环境变量配置（pydantic-settings）
│   │   │   └── rule_loader.py        #   YAML 规则热加载
│   │   ├── llm/
│   │   │   └── openai_compatible.py  #   OpenAI 兼容接口封装
│   │   ├── main.py                   #   FastAPI + Socket.IO 入口
│   │   ├── memory/
│   │   │   ├── short_term.py         #   Redis 会话记忆
│   │   │   └── long_term.py          #   PostgreSQL 长期记忆
│   │   ├── models/
│   │   │   ├── database.py           #   SQLAlchemy ORM 模型
│   │   │   └── schemas.py            #   Pydantic 请求/响应模型
│   │   ├── rag/                      # RAG 检索
│   │   │   ├── embedder.py           #   向量化（OpenAI 兼容）
│   │   │   ├── reranker.py           #   业务规则重排序
│   │   │   └── retriever.py          #   Milvus 向量检索
│   │   ├── tools/                    # Agent 工具集
│   │   │   ├── contact_extractor.py  #   联系方式提取（正则）
│   │   │   ├── product_search.py     #   产品搜索（Tool）
│   │   │   └── user_identifier.py    #   用户识别
│   │   └── utils/
│   │       ├── logger.py             #   结构化日志
│   │       └── privacy.py            #   隐私脱敏
│   ├── config/
│   │   └── agent_rules.yaml          # 意图规则 + 回复模板 + 提示语
│   ├── scripts/
│   │   ├── init_db.sql               # 数据库 DDL
│   │   ├── sync_products.py          # 产品数据同步
│   │   ├── build_vector_index.py     # 向量索引构建
│   │   ├── test_agent.py             # Agent 测试脚本
│   │   └── test_rag.py               # RAG 测试脚本
│   ├── .env.example                  # 环境变量模板
│   └── requirements.txt              # Python 依赖
├── frontend/                         # Vue 3 前端
│   ├── src/
│   │   ├── api/socket.js             #   Socket.IO 客户端
│   │   ├── components/
│   │   │   ├── ChatWidget.vue        #   聊天窗口
│   │   │   ├── ContactForm.vue       #   联系方式收集
│   │   │   ├── MessageInput.vue      #   消息输入框
│   │   │   ├── MessageList.vue       #   消息列表 + 产品卡片渲染
│   │   │   └── ProductCard.vue       #   产品卡片组件
│   │   ├── stores/chat.js            #   Pinia 状态管理
│   │   ├── utils/
│   │   │   ├── privacy.js            #   前端隐私处理
│   │   │   └── storage.js            #   localStorage 工具
│   │   ├── App.vue                   #   根组件
│   │   └── main.js                   #   Vue 入口
│   ├── vite.config.js                # Vite 构建配置（IIFE 输出）
└── └── package.json
```

---

## 4. 快速开始

### 4.1 前置依赖

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Python | ≥ 3.10 | 后端运行 |
| Node.js | ≥ 18 | 前端构建 |
| Docker + Compose | 最新 | 容器化部署 |
| PostgreSQL | 15 | 产品缓存 + 用户数据 + 长期记忆 |
| Redis | 7 | 会话记忆缓存 |
| Zilliz Cloud 账号 | - | 向量检索（Milvus 托管） |
| LLM API 账号 | - | 大模型 + Embedding 调用 |

### 4.2 环境变量配置

复制环境变量模板并填写：

```bash
cp backend/.env.example backend/.env
```

**完整配置项说明：**

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `DATABASE_URL` | ✅ | PostgreSQL 异步连接串 | `postgresql+asyncpg://user:pass@localhost:5432/smart-service_agent` |
| `REDIS_URL` | ✅ | Redis 连接串 | `redis://localhost:6379/0` |
| `REDIS_PREFIX` | - | Redis Key 前缀 | `smart-service-agent:` |
| `ZILLIZ_ENDPOINT` | ✅ | Zilliz Cloud 端点 | `https://xxx.zillizcloud.com` |
| `ZILLIZ_TOKEN` | ✅ | Zilliz 认证 Token | `db_admin:xxx` |
| `ZILLIZ_COLLECTION_NAME` | ✅ | Milvus 集合名 | `smart-service_products` |
| `LLM_API_KEY` | ✅ | 大模型 API Key | `sk-xxx` |
| `LLM_BASE_URL` | ✅ | 大模型 API 地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | ✅ | 模型名称 | `deepseek-v4-flash` |
| `LLM_MAX_TOKENS` | - | 最大输出 Token | `2000` |
| `LLM_TEMPERATURE` | - | 生成温度 | `0.2` |
| `EMBEDDING_API_KEY` | ✅ | Embedding API Key | `sk-xxx` |
| `EMBEDDING_BASE_URL` | ✅ | Embedding API 地址 | `https://api.modelscope.cn/v1` |
| `EMBEDDING_MODEL` | ✅ | Embedding 模型 | `Qwen/Qwen3-Embedding-4B` |
| `EMBEDDING_DIM` | - | 向量维度 | `2560` |
| `MAX_CONTEXT_MESSAGES` | - | 上下文窗口大小 | `10` |
| `CONTACT_COLLECTION_THRESHOLD` | - | 引导留资轮数 | `3` |
| `LOG_DIR` | - | 日志目录 | `logs` |

> **获取 API Key 指引：**
> - **Zilliz Cloud**：注册 [cloud.zilliz.com](https://cloud.zilliz.com)，创建 Cluster 和 Collection，获取 Endpoint + Token
> - **LLM**：DeepSeek (`api.deepseek.com`)、OpenAI (`api.openai.com`) 等任意 OpenAI 兼容接口
> - **Embedding**：ModelScope (`api.modelscope.cn`) 或与 LLM 使用同一服务


### 4.3 本地手动启动

#### Step 1: 数据库

```bash
# 确保 PostgreSQL 和 Redis 已运行
# 执行建表脚本
psql -h localhost -U postgres -d smart-service_agent -f backend/scripts/init_db.sql
```

#### Step 2: 产品数据同步

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv && source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置 .env（见 4.2 节）

# 同步产品数据到 PostgreSQL 并构建向量索引
python scripts/sync_products.py
python scripts/build_vector_index.py
```

#### Step 3: 启动后端

```bash
python app/main.py
# 或
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

服务启动后：
- REST API: `http://localhost:8000/api/health`
- WebSocket: `ws://localhost:8000/socket.io`

#### Step 4: 构建前端

```bash
cd frontend
npm install
npm run build
```

构建产物在 `frontend/dist/`，包含 `chat-widget.js` 和 `chat-widget.css`。

### 4.5 前端 Widget 嵌入

将以下代码插入任意 HTML 页面即可加载聊天组件：

```html
<!-- 在页面底部引入 -->
<link rel="stylesheet" href="/path/to/chat-widget.css">
<script src="/path/to/chat-widget.js"></script>

<!-- 初始化组件 -->
<script>
  window.smart-serviceWidget.init({
    socketUrl: 'http://localhost:8000',  // 后端地址
    locale: 'zh-CN',
  });
</script>
```

---

## 5. API 接口说明

### WebSocket 事件

| 客户端 → 服务端 | 说明 |
|----------------|------|
| `message` | 发送聊天消息 `{ message, session_id, user_id }` |

| 服务端 → 客户端 | 说明 |
|----------------|------|
| `message` | AI 回复 `{ message, session_id, intent, metadata, should_collect_contact }` |
| `status` | 处理状态提示 `{ text }` |
| `contact_collected` | 已提取联系方式 `{ phone?, email? }` |
| `error` | 错误消息 `{ message }` |

### REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | REST 聊天接口 `{ message, session_id?, user_id? }` |
| GET | `/api/products` | 产品列表查询 |

---

## 6. 配置说明

### 6.1 意图规则 (`backend/config/agent_rules.yaml`)

```yaml
# 意图关键词（按优先级排列，从上到下匹配）
intents:
  price_inquiry:
    keywords:
      - 多少钱
      - 最贵
      - 最便宜
      # ... 更多关键词

# 快速通道意图 — 跳过 LLM，直接模板回复
fast_track_intents:
  - greeting
  - thanks
  - farewell
  - capability

# 产品意图 — 走预搜索 + Quick React
product_intents:
  - product_inquiry
  - price_inquiry
  - spec_inquiry
  - recommendation
  - purchase_intent

# 回复模板
templates:
  greeting: "您好，欢迎咨询保军礼品..."
  default: "我已经收到您的需求..."

# 加载提示语
loading_hints:
  analyzing: "正在分析您的问题..."
  searching: "正在为您搜索相关产品..."
  generating: "正在为您整理回复内容..."
```

**自定义意图规则：**
1. 在 `intents` 下新增意图类型和关键词
2. 在 `product_intents` 或 `fast_track_intents` 中注册路由
3. 在 `templates` 中添加对应模板

### 6.2 环境变量 (`backend/.env`)

见 [4.2 节环境变量配置](#42-环境变量配置)。

---

## 7. 脚本说明

| 脚本 | 用途 | 运行方式 |
|------|------|---------|
| `init_db.sql` | 创建表结构（users, sessions, messages, user_memories, products_cache） | `psql` 执行或 Docker 自动加载 |
| `sync_products.py` | 从产品 API 拉取数据 → 写入 PostgreSQL `products_cache` | `python scripts/sync_products.py` |
| `build_vector_index.py` | 将 `products_cache` 数据向量化 → 写入 Zilliz Cloud | `python scripts/build_vector_index.py` |
| `test_agent.py` | Agent 端到端测试 | `python scripts/test_agent.py` |
| `test_rag.py` | RAG 检索测试 | `python scripts/test_rag.py` |

执行顺序：`init_db.sql` → `sync_products.py` → `build_vector_index.py`

---

## 8. 常见问题

### Q: 启动后聊天无回复？
1. 检查 `backend/.env` 中 `LLM_API_KEY` 和 `LLM_BASE_URL` 是否正确
2. 检查 `backend/logs/` 中的日志文件
3. 确认 Redis 和 PostgreSQL 连接正常

### Q: 搜索结果为空？
1. 确认 `sync_products.py` 和 `build_vector_index.py` 已成功执行
2. 检查 Zilliz Cloud Endpoint 和 Token 是否正确
3. 确认 `EMBEDDING_DIM` 与模型实际维度一致（Qwen3-Embedding-4B = 2560）

### Q: 如何更换 LLM 模型？
修改 `backend/.env` 中的 `LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY` 为对应厂商的值。系统通过 OpenAI 兼容接口适配，支持 DeepSeek、OpenAI、Qwen 等任意兼容服务。

### Q: 前端 Widget 如何自定义样式？
1. 修改 `frontend/src/` 中 Vue 组件的 `<style scoped>` 块
2. 重新执行 `npm run build`
3. 替换部署的 `chat-widget.css`

### Q: 如何添加新的 Agent 工具？
1. 在 `backend/app/tools/` 中新建工具类，实现 `execute(db, tool_input)` 方法
2. 在 `orchestrator.py` 的 `self.tools` 字典中注册
3. 工具会自动出现在 ReAct 引擎的 System Prompt 中供 LLM 调用

---

## 9. 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Socket.IO (ASGI) |
| **LLM 接口** | OpenAI 兼容（DeepSeek / OpenAI / Qwen 等） |
| **数据库** | PostgreSQL 15 + asyncpg |
| **缓存** | Redis 7 |
| **向量库** | Zilliz Cloud (Milvus) |
| **前端** | Vue 3 + Pinia + Vite |
| **Markdown** | Marked |
| **容器化** | Docker Compose |
| **配置** | PyYAML + pydantic-settings |

---

## 10. 开发

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/main.py

# 前端
cd frontend
npm install
npm run dev          # Vite 开发服务器
npm run build        # 生产构建（IIFE）
```
