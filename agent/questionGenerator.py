import re
import random

from metagpt.actions import Action, UserRequirement
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message
from .knowCleaner import knowClean, knowCleaner


def parse_json(rsp):
    pattern = r"```json(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    json = match.group(1) if match else rsp
    return json


class questionGeneration(Action):
    PROMPT_TEMPLATE: str = """
        你是医学领域的专业大学教授，现在需要你根据我传递给你的知识点构建一道选择题

        **输出要求:**

        - 我发给你的内容是相关需要生成的试题的知识点
        - 你需要确保你给的题目具有逻辑性且有唯一正确答案
        - 你需要返回题目、选项、答案、解析
        - 题目的表达形式可以有多种，该次生成的题目的表达形式应为：{qtype}。
        - 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠

        **知识库内容:**
        {knowledge_description}

        **输出案例：**

        {{
          "topic": "往无任何神经系统症状，8小时前突发剧烈头痛，伴喷射状呕吐，肢体活动无障碍。应首选以下哪种检查",
          "options": {{
              "A": "头颅X线平片",
              "B": "穿颅多普勒",
              "C": "CT",
              "D": "MRI"
            }},99j
            "answer":"C",
            "parse":"血液溢出血管后形成血肿，大量的X线吸收系数明显高于脑实质的血红蛋白积聚在一起，CT图像上表现为高密度病灶，CT值多高于60Hu。"
        }}

        """

    name: str = "questionGeneration"

    async def run(self, knowledge_description: str):
        chionses = ['直接提问法', '填空法', '是非判断法', '因果推理法', '选择特定选项法', '定义法和应用场景法']
        prompt = self.PROMPT_TEMPLATE.format(knowledge_description=knowledge_description, qtype=random.choice(chionses))
        rsp = await self._aask(prompt)
        text = parse_json(rsp)
        return text


class questionGenerator(Role):
    name: str = "Question generator"
    profile: str = "进行试题的生成"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([questionGeneration])
        self._watch([knowClean])
        # self._watch([UserRequirement])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: 准备执行 {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        context = self.get_memories()
        knowledge_description = await todo.run(context)
        msg = Message(knowledge_description=knowledge_description, role=self.profile, cause_by=type(todo))

        return msg
