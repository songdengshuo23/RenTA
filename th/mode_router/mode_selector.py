from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MODE_1 = "mode_1"
MODE_2 = "mode_2"
INSUFFICIENT_INFO = "insufficient_info"

_SCORE_PATTERNS = (
    re.compile(r"enhanced[_\s-]*score\s*[:=]\s*([0-9.]+)", re.IGNORECASE),
    re.compile(r"llm[_\s-]*score\s*[:=]\s*([0-9.]+)", re.IGNORECASE),
    re.compile(r"score\s*[:=]\s*([0-9.]+)", re.IGNORECASE),
)

_TASK_SIGNAL_ALIASES = (
    ("html", "网页", "页面", "前端", "可视化", "frontend", "visualization", "visualisation", "web"),
    ("地图", "坐标", "路线", "路径", "导航", "地理", "位置", "poi", "geocode", "高德", "map"),
    ("文案", "内容", "社交", "小红书", "朋友圈", "脚本", "种草", "copywriting", "social"),
    ("行程", "计划", "方案", "规划", "日程", "路线", "itinerary", "schedule", "plan"),
    ("预算", "费用", "价格", "成本", "报价", "budget", "cost", "price"),
    ("报告", "攻略", "文档", "总结", "report", "guide", "document"),
    ("质量", "测试", "审查", "校验", "验证", "兼容", "qa", "test", "review"),
    ("数据", "压缩", "清洗", "结构化", "json", "data", "compress"),
)


_ROLE_COVERAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "collect": (
        "collect", "collector", "poi", "source", "search", "retrieve",
        "\u91c7\u96c6", "\u641c\u7d22", "\u68c0\u7d22", "\u83b7\u53d6", "\u666f\u70b9", "\u6253\u5361",
    ),
    "geo": (
        "map", "geo", "geocode", "coordinate", "amap", "route", "navigation",
        "\u5730\u56fe", "\u5750\u6807", "\u9ad8\u5fb7", "\u8def\u7ebf", "\u8def\u5f84", "\u5bfc\u822a",
    ),
    "itinerary": (
        "itinerary", "schedule", "planner", "plan", "travel plan",
        "\u884c\u7a0b", "\u65e5\u7a0b", "\u89c4\u5212", "\u65b9\u6848", "\u4e09\u65e5", "3\u65e5", "\u4e09\u5929", "3\u5929",
    ),
    "content": (
        "content", "copy", "copywriting", "social", "xiaohongshu", "post",
        "\u5185\u5bb9", "\u6587\u6848", "\u793e\u4ea4", "\u5c0f\u7ea2\u4e66", "\u79cd\u8349", "\u670b\u53cb\u5708",
    ),
    "budget": (
        "budget", "cost", "price", "expense", "estimate",
        "\u9884\u7b97", "\u8d39\u7528", "\u6210\u672c", "\u4ef7\u683c", "\u82b1\u8d39",
    ),
    "report": (
        "report", "guide", "document", "summary",
        "\u62a5\u544a", "\u653b\u7565", "\u6587\u6863", "\u603b\u7ed3",
    ),
    "frontend": (
        "frontend", "html", "web", "page", "visual", "visualization", "ui",
        "\u524d\u7aef", "\u53ef\u89c6\u5316", "\u7f51\u9875", "\u9875\u9762", "\u5c55\u793a",
    ),
    "qa": (
        "qa", "test", "review", "quality", "check", "audit",
        "\u8d28\u91cf", "\u6d4b\u8bd5", "\u5ba1\u67e5", "\u6821\u9a8c", "\u9a8c\u8bc1",
    ),
}

_ROLE_COVERAGE_ORDER = ("collect", "geo", "itinerary", "content", "budget", "report", "frontend", "qa")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_score(raw: Mapping[str, Any]) -> float | None:
    for key in ("enhanced_weighted_score", "score", "original_llm_score", "llm_score"):
        score = _safe_float(raw.get(key))
        if score is not None:
            return score

        memo = str(raw.get("memo") or raw.get("reason") or "")
    for pattern in _SCORE_PATTERNS:
        match = pattern.search(memo)
        if match:
            return _safe_float(match.group(1))
    return None


@dataclass(frozen=True)
class CandidateSkill:
    aic: str
    skillid: str = ""
    agent_name: str = ""
    skill_name: str = ""
    score: float | None = None
    ranking: int | None = None
    memo: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CandidateSkill":
        acs = raw.get("acs") or raw.get("parent_agent") or {}
        aic = str(raw.get("aic") or raw.get("agent_id") or "").strip()
        if not aic:
            raise ValueError("candidate skill missing aic")

        return cls(
            aic=aic,
            skillid=str(raw.get("skillid") or raw.get("skillId") or raw.get("id") or "").strip(),
            agent_name=str(raw.get("agent_name") or raw.get("agentName") or acs.get("name") or "").strip(),
            skill_name=str(raw.get("skill_name") or raw.get("skillName") or raw.get("name") or "").strip(),
            score=_extract_score(raw),
            ranking=_safe_int(raw.get("ranking")),
            memo=str(raw.get("memo") or raw.get("reason") or "").strip(),
            raw=dict(raw),
        )


@dataclass(frozen=True)
class TaskHints:
    estimated_skill_count: int | None = None
    requires_independent_roles: bool = False
    requires_negotiation: bool = False
    requires_separate_permissions: bool = False
    cross_organization: bool = False
    parallelizable: bool = False
    user_preference: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "TaskHints":
        if not raw:
            return cls()
        return cls(
            estimated_skill_count=_safe_int(raw.get("estimated_skill_count") or raw.get("estimatedSkillCount")),
            requires_independent_roles=bool(raw.get("requires_independent_roles") or raw.get("requiresIndependentRoles")),
            requires_negotiation=bool(raw.get("requires_negotiation") or raw.get("requiresNegotiation")),
            requires_separate_permissions=bool(raw.get("requires_separate_permissions") or raw.get("requiresSeparatePermissions")),
            cross_organization=bool(raw.get("cross_organization") or raw.get("crossOrganization")),
            parallelizable=bool(raw.get("parallelizable")),
            user_preference=raw.get("user_preference") or raw.get("userPreference"),
        )


@dataclass(frozen=True)
class DecisionConfig:
    relevant_score_threshold: float = 0.55
    fallback_top_n_without_scores: int = 3
    max_relevant_skills_for_mode1: int = 4
    single_agent_coverage_threshold: float = 0.67
    minimum_agents_for_mode2: int = 2
    minimum_skills_for_mode2: int = 3
    max_skills_for_mode2: int = 5

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "DecisionConfig":
        if not raw:
            return cls()
        return cls(
            relevant_score_threshold=_safe_float(raw.get("relevant_score_threshold")) or cls.relevant_score_threshold,
            fallback_top_n_without_scores=_safe_int(raw.get("fallback_top_n_without_scores")) or cls.fallback_top_n_without_scores,
            max_relevant_skills_for_mode1=_safe_int(raw.get("max_relevant_skills_for_mode1")) or cls.max_relevant_skills_for_mode1,
            single_agent_coverage_threshold=_safe_float(raw.get("single_agent_coverage_threshold")) or cls.single_agent_coverage_threshold,
            minimum_agents_for_mode2=_safe_int(raw.get("minimum_agents_for_mode2")) or cls.minimum_agents_for_mode2,
            minimum_skills_for_mode2=_safe_int(raw.get("minimum_skills_for_mode2")) or cls.minimum_skills_for_mode2,
            max_skills_for_mode2=_safe_int(raw.get("max_skills_for_mode2")) or cls.max_skills_for_mode2,
        )


@dataclass(frozen=True)
class ModeDecision:
    mode: str
    label: str
    next_step: str
    summary: str
    reasoning: list[str]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _skill_text(skill: CandidateSkill) -> str:
    acs = skill.raw.get("acs") or skill.raw.get("acp") or {}
    chunks = [
        skill.agent_name,
        skill.skill_name,
        skill.skillid,
        skill.memo,
        str(acs.get("name") or ""),
        str(acs.get("description") or ""),
        str(skill.raw.get("description") or ""),
    ]
    return " ".join(chunk for chunk in chunks if chunk).lower()


def _cjk_bigrams(text: str) -> set[str]:
    chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return {chars[index] + chars[index + 1] for index in range(len(chars) - 1)}


def _task_relevance(task_description: str, skill: CandidateSkill) -> float:
    task_text = str(task_description or "").lower()
    candidate_text = _skill_text(skill)
    if not task_text or not candidate_text:
        return 0.0

    relevance = 0.0
    for aliases in _TASK_SIGNAL_ALIASES:
        task_hit = any(alias.lower() in task_text for alias in aliases)
        skill_hit = any(alias.lower() in candidate_text for alias in aliases)
        if task_hit and skill_hit:
            relevance += 2.0

    ascii_terms = re.findall(r"[a-z0-9][a-z0-9_+#.-]{1,}", task_text)
    relevance += sum(1.0 for term in set(ascii_terms) if term in candidate_text)

    overlap = _cjk_bigrams(task_text) & _cjk_bigrams(candidate_text)
    relevance += min(len(overlap) * 0.15, 1.5)
    return relevance


def _sort_skills(skills: Sequence[CandidateSkill], task_description: str = "") -> list[CandidateSkill]:
    def sort_key(skill: CandidateSkill) -> tuple[float, float, float, float]:
        score = skill.score if skill.score is not None else -1.0
        ranking_score = 1.0 / skill.ranking if skill.ranking else 0.0
        relevance = _task_relevance(task_description, skill)
        relevance_boost = min(relevance * 0.05, 0.25)
        return (score + relevance_boost, relevance, score, ranking_score)

    return sorted(skills, key=sort_key, reverse=True)


def _role_hits(text: str) -> set[str]:
    lowered = str(text or "").lower()
    hits: set[str] = set()
    for role, aliases in _ROLE_COVERAGE_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            hits.add(role)
    return hits


def _skill_roles(skill: CandidateSkill) -> set[str]:
    return _role_hits(_skill_text(skill))


def _required_roles(task_description: str) -> list[str]:
    hits = _role_hits(task_description)
    task_text = str(task_description or "").lower()
    travel_task = any(term in task_text for term in ("\u65c5\u6e38", "\u65c5\u884c", "travel", "trip", "\u884c\u7a0b", "\u8def\u7ebf", "\u65b9\u6848"))
    if travel_task and any(role in hits for role in {"geo", "itinerary", "content", "frontend", "report"}):
        hits.add("collect")
    return [role for role in _ROLE_COVERAGE_ORDER if role in hits]


def _role_match_score(role: str, skill: CandidateSkill) -> float:
    text = _skill_text(skill)
    score = 0.0
    for alias in _ROLE_COVERAGE_ALIASES.get(role, ()):
        if alias.lower() in text:
            score += 1.0
    agent_skill_name = f"{skill.agent_name} {skill.skill_name} {skill.skillid}".lower()
    if role == "collect" and any(term in agent_skill_name for term in ("poi", "collector", "\u91c7\u96c6")):
        score += 4.0
    if role == "geo" and any(term in agent_skill_name for term in ("amap", "geo", "coordinate", "\u9ad8\u5fb7", "\u5750\u6807")):
        score += 4.0
    if role == "itinerary" and any(term in agent_skill_name for term in ("itinerary", "planner", "\u884c\u7a0b", "\u89c4\u5212")):
        score += 4.0
    if role == "content" and any(term in agent_skill_name for term in ("content", "copy", "social", "\u5185\u5bb9", "\u6587\u6848", "\u793e\u4ea4")):
        score += 4.0
    if role == "frontend" and any(term in agent_skill_name for term in ("frontend", "html", "web", "\u524d\u7aef", "\u53ef\u89c6\u5316")):
        score += 4.0
    if role == "report" and any(term in agent_skill_name for term in ("report", "guide", "\u62a5\u544a", "\u653b\u7565")):
        score += 4.0
    if role == "budget" and any(term in agent_skill_name for term in ("budget", "cost", "\u9884\u7b97", "\u8d39\u7528")):
        score += 4.0
    if role == "qa" and any(term in agent_skill_name for term in ("qa", "test", "review", "\u8d28\u91cf", "\u6d4b\u8bd5", "\u5ba1\u67e5")):
        score += 4.0
    return score


def _coverage_sort_key(role: str, skill: CandidateSkill, task_description: str) -> tuple[float, float, float, float, float]:
    score = skill.score if skill.score is not None else -1.0
    ranking_score = 1.0 / skill.ranking if skill.ranking else 0.0
    relevance = _task_relevance(task_description, skill)
    role_score = _role_match_score(role, skill)
    return (role_score, relevance, score, ranking_score, 1.0 if skill.agent_name else 0.0)


def _select_role_coverage_skills(skills: Sequence[CandidateSkill], task_description: str, limit: int) -> list[CandidateSkill]:
    if limit <= 0:
        return []
    ordered = _sort_skills(skills, task_description)
    required = _required_roles(task_description)
    selected: list[CandidateSkill] = []
    selected_aics: set[str] = set()

    for role in required:
        candidates = [skill for skill in ordered if role in _skill_roles(skill) and skill.aic not in selected_aics]
        if not candidates:
            continue
        chosen = sorted(candidates, key=lambda skill: _coverage_sort_key(role, skill, task_description), reverse=True)[0]
        selected.append(chosen)
        selected_aics.add(chosen.aic)
        if len(selected) >= limit:
            return selected

    for skill in ordered:
        if skill.aic in selected_aics:
            continue
        selected.append(skill)
        selected_aics.add(skill.aic)
        if len(selected) >= limit:
            break
    return selected


def _select_relevant_skills(skills: Sequence[CandidateSkill], task_description: str, hints: TaskHints, config: DecisionConfig) -> tuple[list[CandidateSkill], list[str]]:
    ordered = _sort_skills(skills, task_description)
    reasons: list[str] = []
    if task_description:
        reasons.append("Rank candidate skills by registry score plus task-skill text relevance.")

    if hints.estimated_skill_count:
        selected = ordered[: max(1, hints.estimated_skill_count)]
        reasons.append(f"Use estimated_skill_count={hints.estimated_skill_count} from upstream hints to decide how many relevant skills matter.")
        return selected, reasons

    scored = [skill for skill in ordered if skill.score is not None]
    if scored:
        selected = [skill for skill in scored if (skill.score or 0.0) >= config.relevant_score_threshold]
        coverage = _select_role_coverage_skills(ordered, task_description, config.max_skills_for_mode2)
        if selected:
            reasons.append(f"Select relevant skills with score >= {config.relevant_score_threshold:.2f}.")
            merged: list[CandidateSkill] = []
            seen_aics: set[str] = set()
            for skill in coverage + _sort_skills(selected, task_description):
                if skill.aic in seen_aics:
                    continue
                merged.append(skill)
                seen_aics.add(skill.aic)
                if len(merged) >= config.max_skills_for_mode2:
                    break
            if merged:
                reasons.append("Prefer role coverage for mode_2 candidates before filling by score.")
                return merged, reasons

        reasons.append("No skill reached the relevance threshold, so keep only the top scored skill as fallback.")
        return coverage or scored[:1], reasons

    selected = _select_role_coverage_skills(ordered, task_description, max(config.fallback_top_n_without_scores, config.max_skills_for_mode2))
    reasons.append(f"No explicit scores were provided, so keep the first {len(selected)} skills as fallback candidates.")
    return selected, reasons


def decide_mode(task_description: str, skills: Iterable[Mapping[str, Any] | CandidateSkill], hints: Mapping[str, Any] | TaskHints | None = None, config: Mapping[str, Any] | DecisionConfig | None = None) -> ModeDecision:
    normalized_skills: list[CandidateSkill] = []
    for item in skills:
        normalized_skills.append(item if isinstance(item, CandidateSkill) else CandidateSkill.from_mapping(item))

    normalized_hints = hints if isinstance(hints, TaskHints) else TaskHints.from_mapping(hints)
    normalized_config = config if isinstance(config, DecisionConfig) else DecisionConfig.from_mapping(config)

    if not normalized_skills:
        return ModeDecision(
            mode=INSUFFICIENT_INFO,
            label="need_more_skills",
            next_step="collect_more_candidates",
            summary="No candidate skills are available yet, so the router cannot decide between mode_1 and mode_2.",
            reasoning=["The decision layer needs at least one batch of candidate skills from upstream discovery."],
            evidence={"task": task_description, "relevant_skill_count": 0, "distinct_agent_count": 0},
        )

    if normalized_hints.user_preference in {MODE_1, MODE_2}:
        preferred = normalized_hints.user_preference
        return ModeDecision(
            mode=preferred,
            label="user_override",
            next_step="skill_router" if preferred == MODE_1 else "orchestrator",
            summary=f"The user explicitly selected {preferred}.",
            reasoning=["The final routing decision is overridden by an explicit user preference."],
            evidence={"task": task_description, "user_preference": preferred},
        )

    relevant_skills, selection_reasons = _select_relevant_skills(normalized_skills, task_description, normalized_hints, normalized_config)
    if len(relevant_skills) > normalized_config.max_skills_for_mode2:
        relevant_skills = _select_role_coverage_skills(relevant_skills, task_description, normalized_config.max_skills_for_mode2)
        selection_reasons.append(
            f"Cap mode_2 candidate skills at {normalized_config.max_skills_for_mode2} to avoid over-wide orchestration."
        )
    by_agent: dict[str, list[CandidateSkill]] = defaultdict(list)
    for skill in relevant_skills:
        by_agent[skill.aic].append(skill)

    distinct_agent_count = len(by_agent)
    best_agent_aic, best_agent_skills = max(by_agent.items(), key=lambda item: len(item[1]))
    best_agent_skill_count = len(best_agent_skills)
    relevant_skill_count = len(relevant_skills)
    best_agent_coverage = best_agent_skill_count / relevant_skill_count if relevant_skill_count else 0.0

    best_agent_name = next((skill.agent_name for skill in best_agent_skills if skill.agent_name), best_agent_aic)

    hard_mode2_reasons: list[str] = []
    if normalized_hints.requires_independent_roles:
        hard_mode2_reasons.append("The task requires multiple specialist roles to make independent judgments.")
    if normalized_hints.requires_negotiation:
        hard_mode2_reasons.append("The subtasks require negotiation, debate, or mutual review.")
    if normalized_hints.requires_separate_permissions:
        hard_mode2_reasons.append("The task crosses separate permission or responsibility boundaries.")
    if normalized_hints.cross_organization:
        hard_mode2_reasons.append("The task requires cross-organization or cross-vendor collaboration.")
    if normalized_hints.parallelizable and distinct_agent_count >= normalized_config.minimum_agents_for_mode2:
        hard_mode2_reasons.append("The task is parallelizable and the expected parallel gain is likely worth the coordination cost.")

    reasoning = list(selection_reasons)
    agent_skill_counts = {agent_aic: len(agent_skills) for agent_aic, agent_skills in sorted(by_agent.items(), key=lambda item: len(item[1]), reverse=True)}

    if hard_mode2_reasons:
        reasoning.extend(hard_mode2_reasons)
        summary = "Recommend mode_2 because the task has explicit multi-role or multi-responsibility signals."
        mode = MODE_2
        label = "multi_agent"
        next_step = "orchestrator"
    elif relevant_skill_count <= 1:
        reasoning.append("There are not many relevant skills, so a single agent can route them internally.")
        summary = "Recommend mode_1 because one agent should be able to close the loop with a small number of skills."
        mode = MODE_1
        label = "single_agent_multi_skill"
        next_step = "skill_router"
    elif distinct_agent_count == 1:
        reasoning.append("All relevant skills belong to the same agent, so multi-agent coordination would add unnecessary overhead.")
        summary = f"Recommend mode_1 because {best_agent_name} already covers all relevant skills."
        mode = MODE_1
        label = "single_agent_multi_skill"
        next_step = "skill_router"
    elif relevant_skill_count <= normalized_config.max_relevant_skills_for_mode1 and best_agent_coverage >= normalized_config.single_agent_coverage_threshold:
        reasoning.append(f"The strongest single agent covers {best_agent_coverage:.0%} of the relevant skills, which is enough for a single-agent plan first.")
        summary = f"Recommend mode_1 and use {best_agent_name} as the primary agent that calls multiple skills."
        mode = MODE_1
        label = "single_agent_multi_skill"
        next_step = "skill_router"
    elif relevant_skill_count >= normalized_config.minimum_skills_for_mode2 and distinct_agent_count >= normalized_config.minimum_agents_for_mode2:
        reasoning.append("Relevant skills are spread across multiple agents and no single agent cleanly dominates coverage.")
        summary = "Recommend mode_2 because this task is better handled through orchestrated multi-agent collaboration."
        mode = MODE_2
        label = "multi_agent"
        next_step = "orchestrator"
    else:
        if best_agent_coverage >= normalized_config.single_agent_coverage_threshold:
            reasoning.append("Coverage is mixed, but the strongest single agent still covers enough of the task to try a single-agent plan first.")
            summary = f"Recommend mode_1 and let {best_agent_name} attempt the task as the primary agent."
            mode = MODE_1
            label = "single_agent_multi_skill"
            next_step = "skill_router"
        else:
            reasoning.append("Coverage is too fragmented for a reliable single-agent plan.")
            summary = "Recommend mode_2 because the candidate skills are too distributed across agents."
            mode = MODE_2
            label = "multi_agent"
            next_step = "orchestrator"

    evidence = {
        "task": task_description,
        "relevant_skill_count": relevant_skill_count,
        "distinct_agent_count": distinct_agent_count,
        "best_agent": {"aic": best_agent_aic, "name": best_agent_name, "skill_count": best_agent_skill_count, "coverage": round(best_agent_coverage, 4)},
        "agent_skill_counts": agent_skill_counts,
        "selected_skills": [{"aic": skill.aic, "agent_name": skill.agent_name, "skillid": skill.skillid, "skill_name": skill.skill_name, "score": skill.score, "ranking": skill.ranking} for skill in relevant_skills],
        "hints": asdict(normalized_hints),
        "config": asdict(normalized_config),
    }

    return ModeDecision(mode=mode, label=label, next_step=next_step, summary=summary, reasoning=reasoning, evidence=evidence)


def load_payload(input_path: Path) -> dict[str, Any]:
    with input_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    from adapters import normalize_request_payload

    parser = argparse.ArgumentParser(description="Prototype decision layer for mode_1 / mode_2 routing.")
    parser.add_argument("--input", required=True, help="Path to a JSON payload file.")
    args = parser.parse_args()

    payload = load_payload(Path(args.input))
    normalized = normalize_request_payload(payload)
    decision = decide_mode(task_description=normalized["task"], skills=normalized["skills"], hints=normalized["hints"], config=normalized["config"])
    print(json.dumps({"source": normalized["source"], "decision": decision.to_dict()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
