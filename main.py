import fire
from metagpt.logs import logger
from metagpt.team import Team
from agent.knowCleaner import knowCleaner
from agent.questionGenerator import questionGenerator
from utils.generate import MedicalKnowledgeFetcher


keyword = "肾上腺素暴涨"
fetcher = MedicalKnowledgeFetcher()
# 查询糖尿病相关知识
knowledges = fetcher.query_knowledge(keyword)
knowledges = keyword + '\n'.join(knowledges)


async def main(
        idea: str = knowledges,
        investment: float = 100.0,
        n_round: int = 10,
):
    logger.info(idea)

    team = Team()
    team.hire(
        [
            knowCleaner(),
            questionGenerator(),
        ]
    )

    team.invest(investment=investment)
    team.run_project(idea)
    await team.run(n_round=n_round)


if __name__ == "__main__":
    msg = fire.Fire(main)
