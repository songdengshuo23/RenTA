from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


TOPOLOGY_PIPELINE = "pipeline"
TOPOLOGY_TREE = "tree"
TOPOLOGY_HUB_SPOKE = "hub_spoke"
TOPOLOGY_FANOUT_FANIN = "fanout_fanin"
TOPOLOGY_LOOP_REVIEW = "loop_review"


@dataclass(frozen=True)
class TopologyTemplate:
    topology_type: str
    name: str
    description: str
    suitable_for: list[str]
    structure: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_type": self.topology_type,
            "name": self.name,
            "description": self.description,
            "suitable_for": self.suitable_for,
            "structure": self.structure,
        }


def _pipeline_template() -> TopologyTemplate:
    return TopologyTemplate(
        topology_type=TOPOLOGY_PIPELINE,
        name="顺序流水线",
        description="适合天然存在先后顺序的任务，前一节点结果作为后一节点输入。",
        suitable_for=["检索->分析->写作", "步骤天然串行", "需要逐步收敛"],
        structure={
            "root": {"role": "coordinator", "dispatch_mode": "sequential"},
            "nodes": [
                {"id": "step_1", "role": "search", "depends_on": []},
                {"id": "step_2", "role": "analysis", "depends_on": ["step_1"]},
                {"id": "step_3", "role": "writing", "depends_on": ["step_2"]},
            ],
            "merge_policy": "linear_transfer",
        },
    )


def _tree_template() -> TopologyTemplate:
    return TopologyTemplate(
        topology_type=TOPOLOGY_TREE,
        name="树状编排",
        description="一个 root 统筹多个子任务，子任务可并行或部分串行。",
        suitable_for=["多角色独立判断", "root 统一收口", "子任务可拆分"],
        structure={
            "root": {"role": "coordinator", "dispatch_mode": "orchestrated"},
            "nodes": [
                {"id": "child_search", "role": "search", "depends_on": []},
                {"id": "child_analysis", "role": "analysis", "depends_on": []},
                {"id": "child_writing", "role": "writing", "depends_on": []},
            ],
            "merge_policy": "root_summarize",
        },
    )


def _hub_spoke_template() -> TopologyTemplate:
    return TopologyTemplate(
        topology_type=TOPOLOGY_HUB_SPOKE,
        name="中心辐射",
        description="中心节点派发多个独立子任务，子任务回传到中心汇总。",
        suitable_for=["中心节点强协调", "子任务独立", "统一结果收敛"],
        structure={
            "root": {"role": "hub", "dispatch_mode": "broadcast"},
            "nodes": [
                {"id": "spoke_a", "role": "search", "depends_on": []},
                {"id": "spoke_b", "role": "analysis", "depends_on": []},
                {"id": "spoke_c", "role": "writing", "depends_on": []},
            ],
            "merge_policy": "hub_collect",
        },
    )


def _fanout_fanin_template() -> TopologyTemplate:
    return TopologyTemplate(
        topology_type=TOPOLOGY_FANOUT_FANIN,
        name="并行发散-汇聚",
        description="多个子任务并行展开，最后在 join 节点统一合并。",
        suitable_for=["可并行子任务", "需要提速", "多路证据汇总"],
        structure={
            "root": {"role": "dispatcher", "dispatch_mode": "parallel"},
            "nodes": [
                {"id": "branch_1", "role": "search", "depends_on": []},
                {"id": "branch_2", "role": "analysis", "depends_on": []},
                {"id": "branch_3", "role": "writing", "depends_on": []},
                {"id": "join", "role": "coordinator", "depends_on": ["branch_1", "branch_2", "branch_3"]},
            ],
            "merge_policy": "fanin_join",
        },
    )


def _loop_review_template() -> TopologyTemplate:
    return TopologyTemplate(
        topology_type=TOPOLOGY_LOOP_REVIEW,
        name="迭代审阅",
        description="写作与审阅形成闭环，适合需要反复打磨的任务。",
        suitable_for=["论文综述", "报告打磨", "需要多轮修订"],
        structure={
            "root": {"role": "reviewer", "dispatch_mode": "iterative"},
            "nodes": [
                {"id": "draft", "role": "writing", "depends_on": []},
                {"id": "review", "role": "analysis", "depends_on": ["draft"]},
                {"id": "revise", "role": "writing", "depends_on": ["review"]},
            ],
            "merge_policy": "loop_until_converged",
        },
    )


def catalog_topologies() -> list[TopologyTemplate]:
    return [
        _pipeline_template(),
        _tree_template(),
        _hub_spoke_template(),
        _fanout_fanin_template(),
        _loop_review_template(),
    ]


def topology_catalog_dict() -> dict[str, Any]:
    return {"templates": [template.to_dict() for template in catalog_topologies()]}


def select_topology_template(intent: Mapping[str, Any], hints: Mapping[str, Any] | None = None) -> TopologyTemplate:
    hints = hints or {}
    estimated_skill_count = int(hints.get("estimated_skill_count") or intent.get("skills_needed") or 3)
    independent = bool(hints.get("requires_independent_roles") or intent.get("requires_independent_roles"))
    parallelizable = bool(hints.get("parallelizable") or intent.get("parallelizable"))
    needs_review = bool(intent.get("needs_review") or "review" in str(intent.get("task_type") or "").lower())

    if needs_review:
        return _loop_review_template()
    if parallelizable and estimated_skill_count >= 3 and independent:
        return _fanout_fanin_template()
    if independent and estimated_skill_count >= 3:
        return _tree_template()
    if estimated_skill_count <= 2:
        return _pipeline_template()
    return _hub_spoke_template()
