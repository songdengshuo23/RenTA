"""Agent3 — 综述架构撰写与润色定稿智能体"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agent_base import AgentBase


class LiteratureWritingAgent(AgentBase):
    port = 8023
    endpoint = "/agents/literature_writing/rpc"
    group_endpoint = "/group/rpc"
    name = "综述架构撰写与润色定稿智能体"
    partner_aic = os.getenv("PARTNER_AIC", "")
    _max_tokens = 8192

    system_prompt = (
        "你是一位资深的学术综述撰写专家。请基于上游Agent的分析报告，撰写完整的学术综述论文。"
        "结构要求：标题、摘要(200-300字)、关键词、引言、主体章节(>=3章)、结论与展望、参考文献。"
        "格式规范：学术论文标准，Markdown，引用用[1][2]标注。"
        "语言：客观中立，学术风格，每节末尾做简要小结。"
        "末尾标注：本文由多智能体协作系统自动生成(Agent1检索->Agent2分析->Agent3撰写)。"
    )

    @property
    def max_tokens(self) -> int:
        return int(os.getenv("LLM_MAX_TOKENS", str(self._max_tokens)))

    async def validate_input(self, task_input: str) -> tuple:
        if len(task_input) < 200:
            return False, "输入分析报告过短（需>=200字符），请确认已通过Agent2文献精读"
        has_source_marker = any(kw in task_input for kw in [
            "Agent2", "文献精读", "脉络", "观点拆解"
        ])
        if not has_source_marker:
            return False, (
                "拒绝未经过Agent1和Agent2处理链路的直接撰写请求。"
                "请先通过文献检索(Agent1)和文献精读(Agent2)获得结构化分析报告。"
            )
        lower = task_input.lower()
        if any(w in lower for w in ["新闻稿", "博客", "软文", "广告文案"]):
            return False, "不生成非学术体裁的写作内容"
        return True, None

    async def process(self, task_input: str) -> str:
        prompt = (
            "请基于以下分析报告撰写完整学术综述（正文>=2000字）。\n\n"
            "## 分析报告\n\n"
            f"{task_input}\n\n"
            "请严格按以下结构输出：\n"
            "1. 标题\n2. 摘要\n3. 关键词\n4. 引言\n"
            "5. 主体章节(>=3章)\n6. 结论与展望\n7. 参考文献"
        )
        result, usage = await self.call_llm(prompt)
        return result


if __name__ == "__main__":
    LiteratureWritingAgent().run()
