"""Agent1 — 文献检索与初筛智能体"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agent_base import AgentBase


class LiteratureSearchAgent(AgentBase):
    port = 8021
    endpoint = "/agents/literature_search/rpc"
    group_endpoint = "/group/rpc"
    name = "文献检索与初筛智能体"
    partner_aic = os.getenv("PARTNER_AIC", "")
    system_prompt = (
        "你是一位专业的学术文献检索专家。请根据用户的研究主题生成逼真、专业的文献清单。"
        "要求：15-20篇文献，覆盖多个研究方向，标题逼真，作者姓名真实风格，期刊/会议名真实存在。"
        "每篇标注：编号、作者、标题、期刊/会议、年份、研究方向、关联度(高/中)。"
        "末尾标注：以上为Agent1输出的标准化文献清单，可传递给Agent2。"
    )

    async def validate_input(self, task_input: str) -> tuple:
        lower = task_input.lower()
        if any(w in lower for w in ["下载全文", "新闻", "博客", "论坛"]):
            return False, "拒绝非学术来源检索请求（新闻/博客/论坛）"
        if "全文下载" in task_input:
            return False, "不提供文献全文下载服务"
        if len(task_input) < 10:
            return False, "检索主题过于简短（需>=10字符）"
        if len(task_input) > 10000:
            return False, "检索主题过长（需<=10000字符）"
        return True, None

    async def process(self, task_input: str) -> str:
        prompt = (
            f"研究主题: {task_input}\n\n"
            "请生成15-20篇文献的标准化清单，按研究方向分类。"
            "确保每篇标注：编号、作者、标题、期刊/会议、年份、研究方向、关联度(高/中)。"
        )
        result, usage = await self.call_llm(prompt)
        return result


if __name__ == "__main__":
    LiteratureSearchAgent().run()
