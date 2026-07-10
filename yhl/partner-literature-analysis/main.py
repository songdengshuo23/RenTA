"""Agent2 — 文献精读与脉络归纳智能体"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agent_base import AgentBase


class LiteratureAnalysisAgent(AgentBase):
    port = 8022
    endpoint = "/agents/literature_analysis/rpc"
    group_endpoint = "/group/rpc"
    name = "文献精读与脉络归纳智能体"
    partner_aic = os.getenv("PARTNER_AIC", "")
    system_prompt = (
        "你是一位资深的学术文献分析师。请对上游Agent提供的文献清单进行深度分析。"
        "输出要求：\n"
        "1. 核心观点逐篇拆解表（表格：文献|核心方法|创新贡献|局限性|评级）\n"
        "2. 研究发展脉络（分阶段描述）\n"
        "3. 主流流派对比分析（对比表：维度|流派A|流派B|流派C）\n"
        "4. 研究空白与未来方向\n"
        "末尾标注：以上为Agent2输出的脉络综述草稿，可传递给Agent3。"
    )

    async def validate_input(self, task_input: str) -> tuple:
        if len(task_input) < 100:
            return False, "输入文献清单过短（需>=100字符），请确认已通过Agent1检索"
        has_source_marker = any(kw in task_input for kw in [
            "Agent1", "文献检索", "标准化文献清单", "文献清单"
        ])
        if not has_source_marker:
            return False, "拒绝未经过Agent1初筛的原始文献分析请求。请先通过文献检索Agent获得标准化文献清单。"
        lower = task_input.lower()
        if any(w in lower for w in ["原文获取", "下载pdf", "doi解析"]):
            return False, "不提供文献原文获取服务"
        return True, None

    async def process(self, task_input: str) -> str:
        prompt = (
            "请对以下文献清单进行深度精读和脉络分析，输出观点拆解表和研究脉络草稿。\n\n"
            "## 文献清单\n\n"
            f"{task_input}"
        )
        result, usage = await self.call_llm(prompt)
        return result


if __name__ == "__main__":
    LiteratureAnalysisAgent().run()
