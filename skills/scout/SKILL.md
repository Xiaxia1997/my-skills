---
name: scout
description: 从模糊想法/JD/能力缺口出发，自动扩展关键词，在 GitHub/HuggingFace/arXiv 定向检索可学习的开源项目和资源。当用户说"帮我找项目"、"有什么开源的"、"我想学XX"、"这个JD我缺什么"、"怎么补这个能力"、"有没有好的实现"、"找个参考"、"scout"时使用。
---

# Scout - 关键词扩展 + 定向检索

从一个模糊的想法、JD、或能力缺口出发，扩展关键词，在正确的平台上找到可学习的开源项目。

## 核心理念

用户不知道该搜什么 → 你帮他想清楚该搜什么 → 去对的地方搜 → 筛选出值得学的

## 触发场景

- "我想学 XX，有什么好的开源项目？"
- "这个 JD 我哪些能力不够，怎么补？"
- "有没有好的 XX 实现可以参考？"
- "帮我找一下 XX 相关的项目"
- "我想做 XX，有什么现成的可以学？"
- 用户给了一个 JD，想知道怎么准备
- 用户有一个模糊的技术方向，想找实践资源

## 工作流程

### Step 1: 理解意图，提炼核心需求

从用户的输入（可能是一段 JD、一个想法、一个技术方向）中提取：

1. **目标能力**：用户想获得什么能力？（例：GRPO 训练实操、多模态模型微调）
2. **当前水平**：用户已经会什么？（从对话上下文和 memory 推断）
3. **实践性要求**：用户要的是能跑的代码，不是论文综述

输出一句话总结："你想找的是 [XX 领域] 的 [可运行/可学习的] 开源项目，重点关注 [YY 方面]"。输出后直接继续，不要停下来等用户确认；只有当输入存在严重歧义（两种理解会导致完全不同的检索方向）时才提问。

### Step 2: 关键词扩展（核心步骤）

从核心需求出发，向三个维度扩展关键词：

**纵向（深度）**：技术栈的上下游
```
用户说"GRPO 训练" →
  上游: reward model, preference data, SFT baseline
  本体: GRPO, group relative policy optimization, advantage estimation
  下游: evaluation, benchmark, deployment
```

**横向（广度）**：同类/替代/竞品方案
```
用户说"GRPO 训练" →
  同类: DPO, PPO, REINFORCE, RLOO, KTO
  变体: GRPO + CISPO, online GRPO, iterative GRPO
```

**表达变体**：同一概念的不同叫法
```
用户说"GRPO 训练" →
  英文: GRPO training, group relative policy optimization
  缩写: RLHF, alignment training
  口语: reward hacking, policy optimization
  项目名: trl, OpenRLHF, LLaMA-Factory, verl
```

将扩展后的关键词分成 **必搜**（核心）和 **可搜**（扩展）两组。

**arXiv 命名陷阱检查**：扩展关键词后，检查每个关键词是否和其他学科的常用术语撞名。典型陷阱：
- `MiniMax` → 数学优化中的 minimax 定理，搜 arXiv 会全是数学论文。**必须加产品全名**：搜 `MiniMax-M1` 或 `MiniMax-01` 而非 `MiniMax`
- `GLM` → 广义线性模型（Generalized Linear Model），搜 `GLM-5` 或 `ChatGLM`
- `Step` → 阶跃星辰的模型名（Step-2），极易被泛搜吞没，加公司名 `Step AI` 或全名 `Step-2`
- 通用规则：**公司名/产品名如果是普通英文单词（如 Step、Seed、Forge），arXiv 搜索必须加版本号或全名**

**覆盖自检矩阵（防漏搜的关键动作）**：开始搜索前，画一个"子领域 × 资源类型"矩阵。子领域按主题拆（如预训练/SFT/RL），资源类型固定五列：**pipeline 工具、方法论文、数据集、训练框架、awesome 地图**。每个格子至少安排一个搜索动作；确实不适用的格子，在最终输出里显式写"未覆盖+原因"。没有这个矩阵，搜索会顺着惯性滑向自己熟悉的分支（例如只搜数据处理、漏掉整个训练框架侧）。

**awesome 反向补货**：搜到 awesome 列表不能只当一个推荐条目——必须打开浏览目录，把自己候选清单里没有的高频项目补进候选再逐个验证。awesome 是免费的覆盖度外挂。

### Step 3: 定向平台检索

采用**双轮搜索策略**：第一轮按 star 找经典（高 star 的成熟项目），第二轮按时间找前沿（最近 6 个月的新工作）。两轮结果合并后再筛选排序。

**GitHub 和 arXiv 必搜**；其余平台按任务类型选，某个平台明显不相关就跳过，与其硬凑不如不搜。相互独立的搜索在同一条消息里并行发出，不要一个等一个串行跑。

#### 3.1 GitHub（找代码实现）

用 `gh` CLI 搜索，这是最重要的源。**必须跑两轮**：

**第一轮：经典项目（按 star 排序）**
```bash
gh search repos "关键词" --sort stars --limit 10 \
  --json fullName,description,stargazersCount,updatedAt,url
```

**第二轮：前沿项目（按最近更新排序，限最近 6 个月）**
```bash
# 日期动态计算：取当前日期往前推 6 个月
gh search repos "关键词" --sort updated --limit 10 --updated ">$(date -v-6m +%Y-%m-%d)" \
  --json fullName,description,stargazersCount,updatedAt,url

# 如果 date -v 不可用（Linux），用：--updated ">$(date -d '6 months ago' +%Y-%m-%d)"
```

两轮结果去重合并后，再做后续筛选。第一轮捞经典，第二轮捞新星——解决高 star 项目"遮蔽"新项目的问题。

**补充搜索**：
```bash
# 搜代码（找具体实现文件；code search 的 rate limit 很严，报 429/403 就退回仓库搜索）
gh search code "关键词" --language python --limit 10

# 终验单个仓库（注意字段名是 stargazerCount 单数，和 search 的 stargazersCount 不同）
gh repo view owner/repo --json stargazerCount,pushedAt,isArchived,description
```

搜索技巧：
- 核心关键词搜仓库；技术细节关键词（函数名、类名、算法名）搜代码
- `isArchived: true` 的仓库要么淘汰，要么在结果里明确标注"已归档"
- 优先找有完整训练/数据脚本的项目，而不是只有模型定义的
- 第二轮如果某个关键词搜不到新结果，换用扩展关键词再搜一次

#### 3.2 HuggingFace（找模型、数据集、论文、训练示例）

API 优先（结果确定、可排序），WebSearch 兜底：

```bash
# 模型 / 数据集，按下载量排序
curl -s "https://huggingface.co/api/models?search=关键词&sort=downloads&direction=-1&limit=10"
curl -s "https://huggingface.co/api/datasets?search=关键词&sort=downloads&direction=-1&limit=10"

# 论文搜索（Papers with Code 停运后，论文+代码的映射迁移到了 HF Papers）
curl -s "https://huggingface.co/api/papers/search?q=关键词"
```

WebSearch 兜底：`site:huggingface.co/blog "关键词"`（官方教程博客质量高）、`site:huggingface.co/spaces "关键词"`（找可交互 demo）。

#### 3.3 arXiv（找最新研究和方法论）— 默认必搜

arXiv 是追踪前沿方法的核心渠道，**默认必搜**，不要跳过。即使用户"只要代码"，也需要知道最新方法才能搜到对应的代码实现。

用官方 API，返回 Atom XML（标题/摘要/日期齐全）：

```bash
# 按提交时间倒序，优先拿最新论文
curl -s "https://export.arxiv.org/api/query?search_query=all:%22关键词%22&sortBy=submittedDate&sortOrder=descending&max_results=10"
```

**关键**：拿到 arXiv 论文后，用论文标题或方法名去 GitHub 搜对应的代码实现——很多最新论文有官方或社区复现的 repo，但因为太新 star 数还很低，只靠 GitHub star 排序搜不到。

注意：**Papers with Code 已于 2025 年停运**（域名现重定向到 huggingface.co/papers），不要再搜 `site:paperswithcode.com`。"论文找代码"的需求走 HF papers API，或直接拿论文标题搜 GitHub。

#### 3.4 其他按需搜索的源

| 源 | 什么时候搜 | 怎么搜 |
|---|----------|-------|
| Kaggle | 需要数据集或 notebook 实战 | `site:kaggle.com "关键词"` |
| Weights & Biases | 需要训练报告/实验记录 | `site:wandb.ai "关键词"` |
| 知乎/博客 | 需要中文教程解读 | `site:zhihu.com "关键词"` |
| Awesome 列表 | 需要领域全景图 | `gh search repos "awesome 关键词" --sort stars` |

#### 3.5 前沿信息源（捕捉最近 3-6 个月的新工作）

这一步专门解决"经典项目遮蔽新工作"的问题。以下信息源按优先级排序：

**HuggingFace Daily Papers**（最近热门论文，社区投票排序）：
```bash
# 搜索 HF papers（会返回最近被社区关注的论文，含代码链接）
curl -s "https://huggingface.co/api/papers/search?q=关键词"

# 如果 API 没有按时间过滤的参数，用 WebSearch 兜底
# WebSearch: site:huggingface.co/papers "关键词" 2025 OR 2026
```

**主流实验室技术博客**（通过 WebSearch）：
```
site:openai.com/research "关键词"
site:ai.meta.com/blog "关键词"
site:blog.google/technology/ai "关键词"
site:www.anthropic.com/research "关键词"
site:arxiv.org "关键词" 2025 OR 2026
```

不用全搜——只搜和当前主题直接相关的实验室。比如搜预训练数据就不用搜 Anthropic，搜 RL 就重点搜 OpenAI 和 DeepMind。

**中国开源实验室的官方博客必须单独搜**（教训：大量工程细节只发在官网博客/公众号，不在 arXiv 上）：
```
site:minimax.io/news "关键词"          # MiniMax（Forge 框架、M2.1 后训练经验都在这）
site:moonshotai.github.io "关键词"     # Kimi（Kimi-Researcher 等项目页）
site:deepseek.com/blog "关键词"        # DeepSeek
```
HF org 渠道 + arXiv 覆盖论文和模型，但**官方博客覆盖工程实践细节**——两者互补，不能用前者替代后者。特别是 MiniMax，其 Forge 框架（10 万+ scaffold、40× prefix tree 加速）和 M2.1 agent 后训练经验都只发在 minimax.io/news。

**最新顶会论文**（通过 WebSearch）：
```
"关键词" site:openreview.net NeurIPS 2025 OR ICML 2025 OR ICLR 2025 OR ACL 2025
```

拿到论文标题后，一律去 GitHub 搜对应代码实现。

#### 3.6 技术报告扫描（从大模型 Tech Report 里挖实践细节）

现在最前沿的方法往往**不是独立论文，而是藏在大模型技术报告的一两段话里**。比如 Llama 3 报告里的数据清洗 pipeline、DeepSeek-V3 的 RL 策略、Qwen2.5 的多语言数据处理。这些信息搜 GitHub 和独立论文都搜不到。

**报告的信息密度分三个梯队（按学习价值排序）：**

1. **全透明梯队**：AI2 OLMo、HuggingFace SmolLM、NVIDIA Nemotron——数据、代码、配方全开源，报告里每一步都能对着代码和数据看，最适合学实操
2. **详细报告梯队**：DeepSeek、Qwen、Kimi、GLM、MiniMax、小米 MiMo、字节 Seed、腾讯混元、InternLM、Meta Llama——权重开源，报告有大量工程细节（数据 pipeline、RL 配方、超参、ablation），但训练数据本身通常不放
3. **黑盒梯队**：OpenAI / Anthropic / Google 旗舰模型——报告基本不含可复现细节，只看方向，别指望学到 how

**搜索逻辑（和 3.1-3.5 不同，这里是"先知道发布了什么 → 筛报告 → 定向读"）：**

**第一步：先拿"最近发布了什么模型"的全景。禁止凭记忆列模型名——任何写死的模型名单都会过时**

```bash
# HF 全站 trending（当下最热的模型，重要发布都会冒出来）
curl -s "https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=20"

# 按实验室看最近发布（createdAt 倒序 = 该实验室的最新动作）
curl -s "https://huggingface.co/api/models?author=deepseek-ai&sort=createdAt&direction=-1&limit=5"

# HF daily papers（近期社区热议论文，各家技术报告基本都会上榜）
curl -s "https://huggingface.co/api/daily_papers?limit=30"
```

主流开源实验室的 HF org 速查（2026-07 实测全部有效）：
- 中国系（报告细节密度普遍高）：`deepseek-ai`（DeepSeek）、`Qwen`（阿里通义）、`moonshotai`（Kimi）、`zai-org`（智谱 GLM）、`MiniMaxAI`（MiniMax）、`XiaomiMiMo`（小米）、`ByteDance-Seed`（字节）、`tencent`（混元）、`internlm`（上海 AI Lab）
- 西方系：`meta-llama`、`allenai`（OLMo）、`HuggingFaceTB`（SmolLM）、`nvidia`（Nemotron）、`mistralai`、`google`（Gemma）、`microsoft`（Phi）

拿到最新模型名后，用模型名去 arXiv / HF papers 搜对应技术报告（如 `ti:%22kimi%22`）。arXiv 兜底扫描：

```bash
# 技术报告通常标题含 technical report，按时间倒序扫最近一批
curl -s "https://export.arxiv.org/api/query?search_query=ti:%22technical+report%22+AND+cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=15"
```

**arXiv 搜不到的三种情况（必须用 WebSearch 兜底）：**

1. **增量更新无独立论文**：GLM-5.1/5.2 是 GLM-5 的增量更新，没发新 arXiv 论文。搜不到时用 `WebSearch: "模型名" technical report OR release 2026` 查博客/新闻
2. **论文尚未发布**：新发布的模型（如 Kimi K3）可能权重已开源但技术报告延迟数周。在输出中标注"报告待公开"而非假装没有
3. **arXiv 命名碰撞**：`ti:"MiniMax"` 返回全是数学论文。解决方案见 Step 2 的"arXiv 命名陷阱检查"——用产品全名搜 `ti:"MiniMax-M1"`

**第二步：筛选哪些报告值得精读**

- **主题相关性**：报告有没有讲当前主题的专门章节（摘要/目录里搜关键词确认）
- **披露密度**：给了具体数字（数据量、配比、过滤阈值、超参）和 ablation 的才精读；通篇只有 "we filtered low-quality data" 这种一笔带过的略过
- **时效**：优先最近 6 个月；更早的方法大多已被独立论文和开源项目消化，3.1-3.5 会搜到
- **社区关注度**：HF papers 的 upvote 数是不错的代理指标
- **梯队优先**：同等相关时，全透明梯队 > 详细报告梯队 > 黑盒梯队

**第三步：在报告里定向提取（硬性最低配额，不许跳过）**

对筛出的 **top 2-3 份报告，必须实际获取内容**（WebFetch 拉 arXiv abstract 页 / HTML 版 `arxiv.org/abs/xxxx` / 官方博客），每份至少提取 **2-3 个具体数字或方法名**（token 量、数据配比、过滤方法、语言覆盖），并标注出处。只有获取失败（fetch 报错/超时）的报告，才允许降级为"仅列存在性+阅读指引"。

**禁止**用"我没读过所以只列存在性"跳过整个环节——那等于这一步没做。"诚实不编造"约束的是**不写没读到的内容**，不是豁免你去读。

**arXiv 摘要页信息不足时的升级路径**（教训：很多摘要只有高层描述，具体工程细节在全文/博客里）：

1. **先 fetch `arxiv.org/abs/xxxx`**（摘要页），如果拿到的信息不够具体（没有数字/方法名/架构细节）
2. **升级到 fetch `arxiv.org/html/xxxx`**（HTML 全文，信息量远超摘要），如果 HTML 版存在的话
3. **搜官方博客作为补充**：用 `WebSearch: "模型名" 关键词 site:官方域名` 或 `WebSearch: "模型名" 关键词 blog OR technical details`。教训案例：DeepSeek V4 的 agentic RL 细节（DSec 沙箱平台、4 种执行基底）不在 arXiv 报告里，而在 HuggingFace 博客 `huggingface.co/blog/deepseekv4` 里
4. **搜第三方深度分析**：`WebSearch: "模型名" deep dive OR technical analysis`——高质量技术博客（如 philschmid.de、interconnects.ai、sebastianraschka.com）经常比 arXiv 摘要信息更密集

**arXiv 摘要 vs HTML 全文 vs 博客的信息密度差异是巨大的**——同一份报告，摘要可能只说 "a comprehensive post-training pipeline"，HTML 全文会写 "powered by Kubernetes, supports over 10,000 concurrent sandbox instances"，博客会写具体的 Rust 实现和 4 种执行基底。不要在摘要层面就放弃一篇报告。

技术报告的通用结构（定向跳章节用）：
- **Pre-training Data**：数据来源、清洗 pipeline、去重策略、质量过滤、数据配比
- **Post-training / Alignment**：SFT 数据构建、偏好数据、RL 训练策略
- **Evaluation**：评估方法、benchmark 选择
- **Infrastructure / System**：训练框架、执行环境、沙箱架构、rollout 基础设施（这一章经常被忽略但含金量极高）

**第四步：输出时标注来源**

从技术报告里提取的信息，在输出里要明确标注：
```
> 来源：[Llama 3.1 技术报告](arXiv链接), Section 3.1 Pre-training Data
> "We use a quality classifier trained on Llama 2 outputs to filter web data..."
```

用引号标出原文关键句，不要过度推断报告没写的东西。

**注意事项**：
- 技术报告里的方法通常**没有独立代码开源**，但可能有社区复现——提取完后去 GitHub 搜一下是否有人实现
- 有些报告只给了高层描述（如"we used a classifier-based filter"），没有具体细节。这种情况如实写"报告未公开具体实现"，不要脑补
- 优先关注最近 6 个月的报告，更早的报告里的方法可能已经被 3.1-3.5 搜到的独立论文/项目覆盖了

### Step 4: 筛选和排序

对搜到的结果，先做**时间分层**，再在每层内打分筛选：

**时间分层（决定项目归入哪个板块）：**
- **前沿**：最近 6 个月内发布/有重大更新的项目或论文
- **经典**：6 个月前发布但已被广泛验证的项目（高 star、被引用、被后续工作采用）
- 两层都要有内容。如果前沿层搜不到好结果，说明这个领域近期没有重大突破，在输出里明确说明

**必须满足（否则淘汰）：**
- 有可运行的代码（不只是论文/PPT）
- 经典项目：12 个月内仍有维护，或虽停更但方法论仍是基础
- 前沿项目：代码可跑，不要求高 star（新项目 star 少是正常的）

**加分项（按重要性排序）：**
1. **完整训练流程**：从数据处理到训练到评估，不是只有模型定义
2. **方法论新颖性**（前沿项目专用）：相比之前的方法有什么改进/突破
3. **代码可读性**：注释清晰、结构合理、适合学习
4. **社区认可度**：star 数、fork 数、issue 活跃度
5. **文档质量**：README 详细、有使用教程
6. **规模适合学习**：代码量适中（几百~几千行），不是一上来就几万行的工程怪物

**推荐前终验**：对最终要写进结果的每个仓库，跑一次 `gh repo view owner/repo --json stargazerCount,pushedAt,isArchived`，确认 star 数、最近 push 时间、未归档。结果里的 star 数一律以终验为准，不用搜索缓存或记忆里的数字。

**归属交叉核对（终验管不住的错误类型）**：所有"X 团队**发布/提出/属于** Y"的关系型声明（团队↔项目↔数据集↔论文的绑定关系），必须用一次独立检索确认——比如用 `papers/search?q=数据集名` 查作者列表、比对 repo owner。star 数验对了不代表归属是对的：**张冠李戴（把 A 团队的数据集写成 B 项目的产出）是记忆污染的高发模式，也是对读者伤害最大的错误**——读者引用归属错误的信息，一开口就翻车。

**来源性质核验（链接为真 ≠ 来源正确）**：引用"技术报告"前读一眼摘要，确认它确实是**该团队的官方报告**，而不是第三方汇编/综述/复现笔记（摘要里出现 "consolidates publicly reported"、"survey"、"we summarize" 之类措辞就是信号）。把第三方汇编标成官方报告，数字可能没错，但引用出处错了——"XX 官方报告说"变成以讹传讹。

**证据分级**：写进文档的每个事实标一个可信度级别，文末验证声明按级别汇总——
- ✅ 本次实测（命令输出 / API 响应）
- 📄 来自本次读到的论文摘要 / README 原文
- ⚠️ 记忆或推断，未验证（这一级的数字尽量删除或改为定性描述）

### Step 5: 输出结果

按以下格式输出，**经典和前沿分开**，让用户一眼看出哪些是基础、哪些是最新：

```markdown
## 关键词扩展

核心: [列出核心关键词]
扩展: [列出扩展后的关键词]

## 经典必学

这些是经过验证的基础项目，理解原理和核心 pipeline 用。

### 1. [项目名](链接) — ⭐ star 数
一句话说这个项目是什么、为什么值得学。
- 出处：哪家公司/团队/实验室（如 Meta、HuggingFace、清华 NLP）
- 时间：发布/论文时间
- 效果：产出了多大规模的数据？在什么 benchmark 上验证过？被多少后续工作采用？
- 核心价值：你能从中学到什么
- 关键文件：最值得读的几个文件
- 适合程度：★★★★☆

### 2. ...

## 最新前沿

最近 6 个月的新方法、新项目、新论文。Star 可能不高，但代表当前方向。

### 1. [项目名](链接) — ⭐ star 数 | 🆕 YYYY.MM
一句话说这个项目/论文的新突破是什么。
- 出处：团队/实验室
- 时间：发布时间
- 相比之前：对比已有方法（如经典必学里的项目），有什么改进
- 核心价值：你能从中学到什么新东西
- 关键文件：最值得读的几个文件
- 成熟度：🟢 可直接用 / 🟡 需要踩坑 / 🔴 概念验证阶段

### 2. ...

## 来自技术报告的实践细节（如有）

这些信息来自大模型技术报告，通常没有独立代码开源，但代表各家实际在用的方法。

### [模型名] — [报告标题](链接)
> Section X.X: "原文关键句"

- 核心做法：一句话总结他们怎么做的
- 可借鉴点：对学习/面试有什么用
- 社区复现：有无对应的开源实现（有则附链接，无则标注"暂无"）

## 数据集/资源（如有）

- [数据集名](链接) - 什么数据、多大规模

## 方法演进时间线

用一条线串起经典→前沿的方法演进关系，帮助理解"为什么会出现这个新方法"：
```
方法A (YYYY, 团队) → 解决了X问题
  ↓ 但还有Y不足
方法B (YYYY, 团队) → 改进了Y
  ↓ 最新进展
方法C (YYYY, 团队) → 当前SOTA / 新方向
```

## 学习路径（必须含动手任务）

每个子领域至少给一个动手任务，格式："跑什么（具体命令/脚本）→ 改什么 → 产出什么文件"。
能与用户已有项目衔接的（从对话上下文/memory 里找），优先设计成衔接任务。
只有阅读清单、没有动手环节的学习建议视为不合格——用户要补的是实操，"读了四代方法"不等于"做过一份数据"。

## 面试叙事（仅当用户处于求职/面试上下文时生成）

一段第一人称、可直接口述的话术。硬约束：话术中的每个数字、归属、结论必须是 ✅ 或 📄 级证据（见 Step 4 证据分级），⚠️ 级内容禁止进话术——用户会当真去背，错一个归属就翻车。
```

### Step 6: 落盘

检索结果是花了真实成本换来的情报，不要只留在聊天里。如果用户环境有知识沉淀目录（如笔记仓库里的 `inbox/`，或从项目 CLAUDE.md / memory 里能看出类似位置），默认把完整报告写成一份 markdown 存进去，文件名如 `scout-<主题>-<日期>.md`，聊天里给精简版并附上文件路径。找不到知识库目录就只输出聊天，末尾提醒用户可以让你保存。

**服从目标仓库的写入规则，不要自己挑"更合适"的目录**：目标仓库的 README / CLAUDE.md 规定了写入位置（例如"知识沉淀必须先进 inbox"）就严格照做，即使有看起来更贴切的子目录；其他环境找不到明确规则时，写 scratchpad 并告知用户。

## 注意事项

- **不要推荐你不确定存在的项目**。每个推荐都必须是你在 Step 3 中实际搜到并验证过的。
- **不要编造 star 数**。如果不确定，用 `gh repo view` 查一下。
- **优先推荐小而精的项目**。用户要学习的是原理和实操，不是要做生产部署。
- **中英文都搜**。很多好项目的 README 是中文的（尤其是中国开发者的项目）。
- **如果某个平台搜不到有价值的结果，直接说没找到，不要凑数。**

### 从实战中总结的反模式（必须避免）

1. **"arXiv 摘要够用"陷阱**：arXiv 摘要页经常只有高层描述（"a comprehensive pipeline"），具体工程细节（沙箱架构、并发数、执行基底）藏在 HTML 全文或官方博客里。**不要在摘要层面就判定"报告未公开细节"**——先升级到 HTML 全文和博客再下结论
2. **"arXiv 覆盖所有论文"假设**：很多模型的增量更新（GLM-5.1→5.2、DeepSeek V3→V3.1）没有独立 arXiv 论文。工程实践分享（MiniMax Forge、M2.1 后训练经验）往往只在官网博客。**arXiv 搜不到不等于不存在——必须 WebSearch 兜底**
3. **命名碰撞导致搜索失效**：`MiniMax`（公司）vs `minimax`（数学）、`GLM`（模型）vs `GLM`（广义线性模型）、`Step`（阶跃星辰）vs `step`（通用词）。**关键词扩展阶段就要识别并标记碰撞风险**，搜索时用产品全名（如 `MiniMax-M1`）
4. **只搜学术渠道忽略工程渠道**：大模型团队的工程细节分布在至少 4 类渠道——arXiv 论文、HuggingFace 博客、公司官网/GitHub Pages、技术媒体（interconnects.ai/philschmid.de 等）。**只搜 arXiv + GitHub 会系统性漏掉工程实践**
5. **用户提到具体模型名时不逐一检索**：当用户明确列出要查的模型（如"DeepSeek V4、Kimi K3、GLM-5.2、MiniMax"），必须对每个模型名**单独执行一轮搜索**（arXiv + WebSearch + 官方博客），不能靠第一轮的泛搜覆盖。泛搜的召回率对具体模型名远不够
