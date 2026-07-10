# 群聊式多智能体编排方案

## 1. 背景与目标

当前 `th/mode_router` 已经具备以下能力：

- `mode_selector`：根据 skills 数量、角色需求和 hints 判断 `mode_1 / mode_2`
- `orchestrator`：在 `mode_2` 下生成主智能体为根、子智能体为叶的树形计划
- `literature_workflow`：可实际跑通 `discovery -> 路由 -> 编排 -> 智能体调用 -> 结果落盘`

当前主要问题不是“能不能跑”，而是：

1. 子智能体协作仍以串行为主，网络协作感不足
2. 第三个 Agent 输出慢，用户体感差
3. 主智能体目前更像调度器，不像“群主 + 仲裁者”
4. 当前“反馈机制”虽然形式上存在，但跑完后对子智能体输出没有形成稳定的实质性修改闭环，需要单独检查与修复

本方案目标：

1. 在保留现有 `mode_selector + orchestrator` 的前提下，引入“群聊式多智能体协作”
2. 让主智能体负责选人、建群、控轮次、控收敛
3. 让子智能体支持围绕共享黑板进行有限群聊，而不是单纯串行传结果
4. 第一阶段先保证“能稳定跑通”，再逐步增强网络感
5. 第一阶段优先聚焦一个核心问题：第三个 Agent 输出慢且反馈未真正驱动修改，先把这条链查清并跑顺，再追加更复杂的群聊增强

## 2. 总体思路

不是推翻现有树形结构，而是升级为：

- **控制结构**：树
- **通信结构**：群
- **共享状态结构**：黑板

即：

- 树负责表示“谁受谁管理”
- 群负责表示“谁和谁可以交互”
- 黑板负责表示“大家共同读写什么状态”

可以概括为：

`Tree for control + Group chat for collaboration + Blackboard for shared state`

## 3. 适用范围与启动条件

### 3.1 什么时候仍然走 mode_1

满足以下任一条件时，继续走 `mode_1`：

1. 候选 skills 很少，`relevant_skill_count <= 2`
2. 同一个 Agent 覆盖了大部分关键 skills
3. 用户任务本质是单环闭合任务，不需要多角色独立判断
4. 下游执行要求极强一致性，容忍不了多智能体讨论噪声

### 3.2 什么时候走 mode_2 + 群聊协作

满足以下条件时，进入“群聊式多智能体协作”：

1. `distinct_agent_count >= 2`
2. `estimated_skill_count >= 3`
3. 用户任务可自然拆成多个角色视角，例如：
   - 检索
   - 分析
   - 写作
   - 质检
4. 任务允许部分结果并行探索，而不是严格等上一步完成
5. 任务需要多方补证据、互相解释、互相修正

### 3.3 第一阶段的限制条件

为了先跑通，第一阶段建议加硬限制：

1. 群成员上限：`3~4` 个核心子智能体
2. 最大发言轮次：`4` 轮
3. 所有消息都先经过主智能体转发，不做真正点对点直连
4. 子智能体只能围绕固定黑板字段发言，不能无限散聊
5. 如果某轮没有新增有效信息，主智能体直接收敛

## 4. 角色设计

### 4.1 主智能体（Orchestrator / Coordinator）

主智能体不负责大量内容生产，核心职责是：

1. 读取用户任务
2. 调用 discovery 获取候选 Agent/skills
3. 调用 LLM 做任务拆解与角色识别
4. 给每个角色选出最合适的子智能体
5. 创建群会话
6. 发布议题与轮次规则
7. 维护共享黑板
8. 汇总冲突、做最终仲裁
9. 决定是否结束讨论并进入成稿

### 4.2 子智能体

第一阶段建议固定 3 类核心角色：

1. `search`
   - 负责检索、初筛、补检索
2. `analysis`
   - 负责脉络、观点、分类、争议分析
3. `writing`
   - 负责框架、正文、润色、收束

后续可扩展：

4. `review`
5. `fact_check`
6. `timeline`
7. `taxonomy`
8. `gap`

## 5. 选人逻辑：如何使用现有 orchestrator

现有 `orchestrator` 不废弃，直接升级。

### 5.1 输入不变

保留当前输入：

- `task_description`
- `selected_skills`
- `decision`
- `hints`

### 5.2 输出升级

当前 `plan` 主要包含：

- `coordinator`
- `work_packages`
- `orchestration_tree`

建议升级为：

```json
{
  "coordinator": {},
  "group_plan": {},
  "execution_plan": {},
  "orchestration_tree": {}
}
```

### 5.3 角色选择逻辑

不是简单选 Top-K Agent，而是“按角色选最合适 Agent”。

具体步骤：

1. LLM 根据任务识别需要哪些角色
2. orchestrator 根据候选 skills 给每个角色打分
3. 每个角色选 1 个主成员
4. 如有候选重复过多，做去重与替补

#### 推荐打分项

每个候选 Agent 对某角色的分数可以由以下部分构成：

1. `skill_match_score`
   - 候选 skill 与角色目标的匹配度
2. `agent_description_score`
   - Agent 描述与角色职责的语义匹配度
3. `role_uniqueness_bonus`
   - 与已选成员能力重复少则加分
4. `execution_stability_score`
   - 历史调用稳定性 / 返回速度 / 成功率

### 5.4 建议的成员层级

为了防止群太乱，建议分层：

1. `core`
   - 必进群，持续发言
2. `reserve`
   - 候补成员，只在需要时被拉入
3. `observer`
   - 只读黑板，不主动发言

第一阶段只实现 `core + reserve` 即可。

## 6. 群聊会话模型

### 6.1 GroupSession

建议由主智能体创建：

```json
{
  "group_id": "grp-xxx",
  "topic": "任务主题",
  "coordinator": {
    "aic": "...",
    "name": "..."
  },
  "members": [],
  "round_index": 0,
  "status": "active"
}
```

### 6.2 Message

统一消息格式：

```json
{
  "message_id": "msg-xxx",
  "group_id": "grp-xxx",
  "sender_role": "analysis",
  "sender_agent": "文献分析智能体",
  "target": "group",
  "type": "request_more_evidence",
  "content": "2019-2021阶段文献证据不足，请补检索",
  "reply_to": "msg-yyy",
  "round": 2,
  "timestamp": "2026-05-18T09:00:00Z"
}
```

### 6.3 第一阶段允许的消息类型

建议先限制为：

1. `proposal`
2. `request_more_evidence`
3. `clarification`
4. `draft_update`
5. `conflict_report`
6. `final_commit`

不允许无限制自由对话。

## 7. 共享黑板设计

第一阶段共享黑板字段建议固定：

```json
{
  "task": "",
  "candidate_papers": [],
  "accepted_papers": [],
  "timeline_draft": [],
  "taxonomy_draft": [],
  "gap_candidates": [],
  "section_outline": [],
  "section_drafts": {},
  "open_questions": [],
  "conflicts": [],
  "final_constraints": {}
}
```

### 字段使用建议

1. `search`
   - 写 `candidate_papers / accepted_papers`
2. `analysis`
   - 写 `timeline_draft / taxonomy_draft / gap_candidates`
3. `writing`
   - 写 `section_outline / section_drafts`
4. `coordinator`
   - 维护 `open_questions / conflicts / final_constraints`

## 8. 运行流程

### 阶段 1：发现与建群

1. 用户发起任务
2. 主智能体调用 discovery 获取候选 Agent/skills
3. 主智能体调用 LLM 识别角色需求
4. orchestrator 为每个角色选人
5. 创建 `group_plan`

### 阶段 2：首轮发言（Opening Round）

主智能体同时给每个核心子智能体一个初始任务卡：

1. `search`：先给候选文献和初筛结果
2. `analysis`：先给阶段划分 / 分类草图 / 待验证观点
3. `writing`：先给综述框架与章节骨架

这一阶段允许并发。

### 阶段 3：有限轮次讨论（Discussion Rounds）

每轮由主智能体控制：

1. 收集子智能体消息
2. 更新共享黑板
3. 判断是否需要：
   - 补检索
   - 修正分类
   - 细化某章节
4. 决定下一轮允许谁发言

### 阶段 4：收敛

主智能体满足以下条件时可收敛：

1. 黑板关键字段已填满
2. `open_questions == 0`
3. `conflicts` 数量降到阈值以内
4. 达到轮次上限

### 阶段 5：成稿与交付

1. `writing` 根据黑板出最终稿
2. 主智能体做最终审阅
3. 产出：
   - `group_plan`
   - `message_log`
   - `blackboard_snapshot`
   - `final_output`

## 9. 提示词模板建议

### 9.1 主智能体：角色拆解与选人提示词

```text
你是一个多智能体群聊编排器。

输入：
1. 用户任务
2. discovery 返回的候选 agents 和 skills

你的任务：
1. 识别完成该任务所需的关键角色
2. 为每个角色选择最合适的 agent
3. 输出 group_plan

约束：
1. 第一阶段核心成员不超过 4 个
2. 优先选择能力互补、职责清晰的 agent
3. 如果多个角色被同一 agent 覆盖，优先保证角色分工清晰
4. 输出必须包含：
   - coordinator
   - members
   - member_roles
   - interaction_rules
   - turn_policy
   - blackboard_schema
```

### 9.2 子智能体：入群初始任务卡模板

```text
你现在是群聊协作中的 {role} 角色。

全局任务：
{task}

你的职责：
{role_objective}

当前共享黑板摘要：
{blackboard_snapshot}

你本轮只能执行以下动作之一：
1. proposal
2. request_more_evidence
3. clarification
4. draft_update
5. conflict_report
6. final_commit

输出格式（JSON）：
{
  "type": "...",
  "target": "group 或 指定角色",
  "content": "...",
  "blackboard_update": {}
}
```

### 9.3 主智能体：轮次收敛判断模板

```text
你是群聊主持人。

请根据以下信息判断：
1. 是否进入下一轮讨论
2. 是否触发补检索
3. 是否直接进入最终写作

输入：
1. 当前轮次消息
2. 当前黑板状态
3. 当前未解决问题列表

输出：
{
  "continue_discussion": true/false,
  "next_speakers": [],
  "need_more_evidence": true/false,
  "updated_open_questions": [],
  "decision_summary": "..."
}
```

## 10. 与当前代码的映射建议

### 10.1 `mode_selector.py`

保持现状，仅补充 hints 口径：

- `requires_group_chat`
- `max_group_members`
- `max_discussion_rounds`

### 10.2 `orchestrator.py`

从当前的：

- `coordinator`
- `work_packages`
- `orchestration_tree`

升级为：

- `coordinator`
- `group_plan`
- `execution_plan`
- `orchestration_tree`

### 10.3 `literature_workflow.py`

第一阶段先做最小兼容：

1. 保持现有落盘逻辑
2. 新增：
   - `group_plan.json`
   - `message_log.json`
   - `blackboard_snapshot.json`

### 10.4 `service.py`

扩展 `mode_2` 返回值：

1. `plan`
2. `group_plan`
3. `zh.plan`

## 11. 第一阶段最小可运行版本

为了“先想怎么跑通”，建议第一阶段只做以下范围：

1. 主智能体用 LLM 决定群成员和角色
2. 主智能体创建 `group_plan`
3. 主智能体按轮次依次收集子智能体结构化消息
4. 所有群消息都先经过主智能体
5. 共享黑板只维护固定字段
6. 最多 3 个核心子智能体，最多 4 轮讨论
7. 单独增加“反馈闭环检查”步骤，重点验证：
   - 第三个 Agent 是否收到来自前序节点或主智能体的明确反馈
   - 反馈是否真正进入 prompt 或共享黑板
   - 第三个 Agent 的最终输出是否因反馈发生了可观测修改

### 11.1 第一阶段的唯一优先问题

根据当前组内要求，第一阶段不要同时追求“完整群聊网络能力”与“复杂横向协作”。  
优先只解决下面这一条：

**可以跑，但第三个 Agent 输出依旧慢，而且所谓反馈没有形成实质修改。**

因此建议先把问题拆成 3 个检查点：

1. **调用链检查**
   - 第三个 Agent 是否被稳定调用
   - 调用前是否拿到了足够的上下文

2. **反馈注入检查**
   - 主智能体或前序 Agent 的反馈是否真的写入了第 3 个 Agent 的输入
   - 反馈是否只是日志存在，而没有进入实际 prompt

3. **修改效果检查**
   - 第 3 个 Agent 的二次输出相比初次输出，是否有结构、内容或证据层面的明显变化
   - 如果没有变化，要么反馈不够具体，要么反馈没有被真正消费

也就是说，第一阶段建议把“群聊式编排”先收缩为：

- 主智能体可管理
- 子智能体可被选中
- 反馈能真正驱动第 3 个 Agent 修改输出

只要这一条跑顺，再继续追加更复杂的群聊能力。

这样做的好处：

1. 复杂度可控
2. 容易调试
3. 已经能体现“智能体网络感”
4. 不会一下子把当前可运行流程打碎

## 12. 结论

本方案不推翻现有架构，而是在当前 `mode_2` 树形编排基础上，升级为：

1. 主智能体负责选人、建群、控轮次、控收敛
2. 子智能体围绕共享黑板进行有限群聊
3. 通过固定消息类型、固定轮次和固定黑板字段，先保证“能跑通”

建议实施顺序：

1. 先扩 `orchestrator` 输出 `group_plan`
2. 再加共享黑板
3. 再加消息日志
4. 最后再开放更复杂的横向交互

这样既满足“组长要求给出限制条件、调用方式和提示词模板”，也符合当前项目“先跑通，再增强”的现实目标。
