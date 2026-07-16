# PROJECT_NOTES — 好想上岸 / JD-Scout 交接文档

> **这份文档给 Claude Code 看的**。项目发起人 Ziming(Alan)在完全独立的机器(Mac)上开新的会话,不会有之前的对话上下文。所有关键决策、红线、战略考量都在这份文档里。**开工前完整读一遍,不要跳过任何小节**。

---

## 0. 一句话总结

**好想上岸(JD-Scout)** 是一个用 LangGraph 做的 AI Agent,帮求职者把每一份岗位 JD 看穿看透:自动抓取 JD → 结构化提取需求 → 与用户简历做 gap 分析 → 生成简历改写建议和面试重点。

**中文名**:好想上岸(情绪拉满的求职圈黑话,社区传播用)
**英文名 / repo 名**:jd-scout(GitHub 收录用,反用 HR 的 headhunt "scouting" 概念)
**目标用户**:秋招/春招求职者,首个用户就是项目发起人自己

---

## 1. 项目发起人背景(为什么做这个)

- **Ziming (Alan)**,Northeastern Align MCS 在读,预计 2026 年底毕业
- 本科 Tulane Finance,现在秋招目标是**深圳的 AI Agent 工程师岗位(FinTech 方向为主)**
- **他自己正在秋招投几十家公司**,每份 JD 3 分钟读不完,简历要针对不同岗位改累死 —— **他就是首个用户**
- 这个项目同时是他简历上的**主打 AI Agent 项目**,需要:能 demo、有 star 潜力、每一行代码都是他自己写的

**这个"我自己就是用户"的属性极其重要**。任何设计决策、功能优先级都要围绕"Ziming 每天秋招真的会用到吗"来判断。

---

## 2. 项目要证明什么(简历/面试视角)

面试 AI Agent 岗高频要求:

| JD 高频关键词 | 项目要怎么覆盖 |
|---|---|
| Prompt Engineering ⭐ | 4 个节点各自的 prompt 精心设计 |
| Tool Use / Function Calling ⭐ | JD 抓取工具、PDF 解析工具都做成 LangChain tool |
| LangGraph ⭐ | 项目核心,不能替换成别的框架 |
| Multi-node Workflow ⭐ | 4 节点主流程,可扩展 |
| Structured Output(Pydantic) ⭐ | JD 需求、gap 分析、改写建议都必须 Pydantic 强约束 |
| PDF 文档解析 ⭐ | 简历上传后解析 |
| 网页抓取 | JD 网页抓取(BOSS/拉勾/Lever/LinkedIn) |
| Docker | 部署必用 |
| RAG + 向量库(Phase 2) | Chroma 存历史投递记录,做同类岗位匹配 |
| Memory 机制(Phase 2) | 用户简历版本记录 + 历史投递 |

**Phase 1(MVP)覆盖前 7 项。Phase 2 补齐向量库和 Memory,达到 9/10 覆盖率**。

---

## 3. 诚实红线(必须遵守)

### 3.1 从零写,不 fork 任何开源项目

这次项目**从零开始**。所有代码都要是 Ziming 自己写的(通过 Claude Code 协作)。**禁止**:
- 不能 fork LangChain 官方的 `langchain-templates`、`open_deep_research` 之类的项目
- 不能大段照抄 GitHub 上其他 JD 分析工具的代码
- 参考现有实现思路可以,但代码必须自己重新写一遍

**理由**:面试官问细节的时候,他要能自信讲每一行代码为什么这么写。之前另一个项目(AgentInvest)因为是 fork 别人的,已经踩过这个坑,不能再犯。

### 3.2 每个技术决策必须有明确理由

Claude Code 在做技术选型时,不要用"因为它更好"或"业界标准"作为理由。每个选型要有具体的 trade-off 说明,写到代码注释里。理由是:面试深挖时"你为什么用 X 不用 Y"是最高频的问题。

例子:
- ✅ 好的注释:`# 用 pdfplumber 不用 pypdf: pypdf 对多列排版会把两列文字混行, pdfplumber 保序`
- ❌ 差的注释:`# 用 pdfplumber 解析 PDF`

### 3.3 API key 不能进 git

- 用 `.env` 管理,`.gitignore` 里明确列出
- `.env.example` 里放占位符
- 不要在日志里打印 key 片段(Ziming 之前另一个项目泄露过 DeepSeek key,教训)

### 3.4 用户上传的 PDF 隐私

- MVP 阶段不持久化用户简历,处理完就丢
- Phase 2 如果加向量库存历史,必须明确告诉用户"数据本地保存"
- 不要把用户简历原文发到第三方 API(除了 LLM 推理必需的场景)

---

## 4. 核心设计决策(不要挑战)

### 4.1 优先 CLI,再加 Web UI

**MVP 用 CLI 交互**,不做 web 前端。理由:
- 降低前期复杂度,专注核心 LangGraph 工作流
- Ziming 自己是开发者,CLI 也用得舒服
- Web UI 放 Phase 2,做起来快,不影响 MVP 验证

### 4.2 LLM 选 DeepSeek

- Ziming 已经有 DeepSeek API key,便宜(比 OpenAI 便宜 10-20 倍)
- DeepSeek-V3 的能力对这个任务够用
- **但代码要用 `init_chat_model` 或 OpenAI-compatible 接口封装**,方便切换到其他模型
- 注意:DeepSeek max_tokens 上限 8192,长文档要分片

### 4.3 网页抓取工具选型

- **默认用 `requests + BeautifulSoup`**(轻量,适合 90% 的普通 HTML)
- **fallback 用 Playwright**(处理 JS 渲染的网站,如 BOSS 直聘的动态加载)
- 不用 Selenium(依赖重、云端不稳定,之前另一个项目踩过坑)
- 不用 crawl4ai(太重,MVP 不需要)

### 4.4 PDF 解析选型

- **用 `pdfplumber`**(处理多列排版和表格好于 `pypdf`)
- 简历大概率是单列格式,pdfplumber 完全够用
- 不用 LandingAI ADE(付费 API,MVP 不需要外部依赖)

### 4.5 向量库选型(Phase 2)

- **用 Chroma**(轻量,本地文件持久化,零配置)
- 不用 Milvus/Qdrant(需要单独部署,MVP 复杂度太高)
- embedding 用 DeepSeek 的 embedding API 或 sentence-transformers 本地模型

### 4.6 部署形态

- **Docker + Docker Compose**(和用户简历上其他项目一致)
- **不放 Hugging Face Space**(HF Space 主要给 Gradio/Streamlit,LangGraph 生态不匹配)
- **放 GitHub**,用户能一键 clone + `docker compose up` 跑起来
- README 里放一段 demo 视频/GIF,展示"输入 JD → 输出建议"

---

## 5. 目录结构(初始化时按这个建)

```
jd-scout/
├── README.md                    # 英文,GitHub 首屏
├── README-CN.md                 # 中文,"好想上岸"版本
├── PROJECT_NOTES.md             # 本文件,项目交接
├── PHASE_1_BLUEPRINT.md         # Phase 1 详细实施方案
├── LICENSE                      # MIT
├── .gitignore                   # 必须包含 .env, __pycache__, *.pyc
├── .env.example                 # API key 占位符
├── pyproject.toml               # Python 依赖 (uv 或 poetry)
├── Dockerfile
├── docker-compose.yml
├── src/
│   └── jdscout/
│       ├── __init__.py
│       ├── graph.py             # LangGraph 主图,把 4 节点串起来
│       ├── state.py             # AgentState + Pydantic schemas
│       ├── config.py            # 配置管理(读 .env)
│       ├── cli.py               # CLI 入口: `python -m jdscout <jd_url>`
│       ├── nodes/
│       │   ├── __init__.py
│       │   ├── fetch_jd.py      # Node 1: 抓取 JD (URL 或原文)
│       │   ├── extract.py       # Node 2: 结构化提取
│       │   ├── analyze.py       # Node 3: 简历 gap 分析
│       │   └── advise.py        # Node 4: 生成改写建议
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── web_scraper.py   # 网页抓取
│       │   └── pdf_parser.py    # PDF 解析
│       └── prompts/
│           ├── __init__.py
│           └── templates.py     # 4 个节点的 prompt 模板
├── tests/
│   ├── __init__.py
│   ├── test_fetch.py
│   ├── test_extract.py
│   └── fixtures/
│       ├── sample_jd.html
│       └── sample_resume.pdf
└── examples/
    ├── sample_jd.txt
    └── sample_resume.pdf
```

**关键点**:
- Python 包名用 `jdscout`(小写,无横线,符合 PEP 8)
- Repo 名用 `jd-scout`(带横线,GitHub 惯例)
- 所有 src 代码放 `src/jdscout/` 下(src-layout,是 2025 年 Python 打包最佳实践)

---

## 6. 目标里程碑

### Phase 0(半天):环境搭建 + hello world
- 项目骨架初始化
- 装依赖(langgraph, langchain, pydantic, pdfplumber, beautifulsoup4, requests, python-dotenv, uvicorn)
- 一个最简单的 hello world 图跑通(1 节点,输入输出)
- Docker 能 build 起来

### Phase 1(1 周):MVP 4 节点工作流
- 4 个节点全部跑通
- CLI 可以用:`jdscout <jd_url> <resume_pdf>`
- 输出结构化的 JSON 报告(JD 需求 + gap 分析 + 改写建议)
- 至少一份端到端测试用例(用 fixture 里的 sample)
- **详细任务清单见 PHASE_1_BLUEPRINT.md**

### Phase 2(1 周):增强
- Web UI(FastAPI + 简单 HTML,风格参考 StudyPath AI)
- Chroma 向量库存历史投递
- 同类岗位智能匹配("你之前投过 3 个类似的...")
- 简单 memory:记住用户简历版本

### Phase 3(3-5 天):打磨 + 推广
- README 精修(英文 + 中文)
- 录一段 30 秒 demo 视频/GIF
- 发到:小红书 / B 站 / v2ex / 脉脉 / Twitter
- 目标:秋招期间自然增长到 50+ star

---

## 7. 面试话术(项目做完后能这样讲)

**"这个项目是怎么想到的?"**
> "我自己秋招投几十家公司,发现两个真实痛点:JD 太多看不完,每份 3 分钟;同一份简历应对不同岗位人工改累死。所以我做了个 Agent 帮我筛选和改写。技术上是 LangGraph 4 节点工作流:抓取 JD → 结构化提取需求(Pydantic 强约束)→ 简历 gap 分析 → 生成改写建议。**我自己每天在用,分析过 XX 个 JD,准确率 XX%(等有真实数据填)**。"

**"为什么用 LangGraph 不用 Chain 或者自己写?"**
> "三个原因:第一,4 个节点之间需要共享 state(简历、JD 结构化数据、gap 分析结果),用 LangGraph 的 State 管理比手动传参干净;第二,后续可能加分支(比如 JD 类型分类走不同 prompt 路径),conditional edge 用起来方便;第三,可观测性 —— astream_events 让我能实时看每个节点跑到哪、耗时多少,方便调优。"

**"Pydantic 强约束具体做了什么?"**
> "两个地方:JD 提取节点输出必须符合 `JDRequirements` schema(hard_skills、years、education 都是必填),简历 gap 分析输出必须符合 `GapAnalysis` schema(matched、missing、should_emphasize 三个字段)。LangGraph 的 structured output 如果模型返回不符合,会自动 retry;超过 3 次就走 fallback,写到 log 里让我人工看。这样能保证下游节点拿到的数据可预期。"

**"你觉得这个项目还有哪些不足?"**(诚实展示反思能力)
> "三个:第一,网页抓取对反爬弱,BOSS 直聘偶尔要手动粘 JD 文本;第二,简历改写建议现在偏保守,不敢改动力度太大;第三,现在只支持中英文,多语言没做。"

---

## 8. 常见坑与防御

- **DeepSeek 8192 max_tokens 上限**:长 JD + 简历 + prompt 很容易超,需要**分片处理或截断**
- **反爬**:招聘网站有反爬机制,requests + BeautifulSoup 拿不到内容是常事,需要 fallback 到"用户手动粘贴 JD 文本"
- **PDF 简历排版多样**:双列、图片版、扫描版都可能遇到,MVP 只保证单列文字 PDF 正常
- **LLM 幻觉**:JD 提取时可能编造 skill,`Pydantic + structured output + retry` 一定要做
- **异步**:LangGraph 的节点用 `async def`,不要混同步和异步(会 deadlock)

---

## 9. 检查清单(每个 phase 完成前)

- [ ] `grep -r "TODO\|FIXME" src/` 没有遗留待办
- [ ] `.env` 不在 git 里(`git check-ignore .env` 应返回路径)
- [ ] `docker compose up` 能起服务
- [ ] `pytest tests/` 全通过
- [ ] README 更新到当前 phase 完成状态
- [ ] 至少 1 个真实的端到端用例跑过(不是 mock 数据)

---

## 10. 决策记录(为什么这么做)

- **为什么中英文双名**:中文"好想上岸"传播友好但英文语境不通(OnboardingAid 会被误解成 HR 员工入职工具);英文 JD-Scout 语义精准但中文不好传播。双名各司其职
- **为什么不做 Web UI 优先**:MVP 阶段重点是让 LangGraph 工作流跑通,web UI 是包装。先让核心 agent 能用,包装可以后加
- **为什么放 GitHub 不放 HF Space**:HF Space 主推 Gradio/Streamlit 生态,LangGraph 部署不友好;GitHub 加 Docker + README + demo 视频是 LangGraph 项目的标准展示方式
- **为什么从零写不 fork**:面试深挖时能自信讲每一行代码;之前 fork 别人的项目已经证明会被追问细节到崩溃

---

## 11. 联系信息

- **发起人**:Ziming (Alan),GitHub `AlanYy-42`
- **邮箱 / 其他**:项目发起人自己填

---

**最后一句提醒**:这个项目的**关键成功因子不是技术炫技**,是**"我自己每天在用"**。任何时候技术决策产生冲突,选那个"让 Ziming 更愿意每天用"的方向。用户价值 > 技术漂亮度。
