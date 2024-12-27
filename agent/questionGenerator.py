import random
import re

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message

from .knowCleaner import knowClean


def parse_json(rsp):
    pattern = r"```json(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    json = match.group(1) if match else rsp
    return json


class questionGeneration(Action):
    PROMPT_TEMPLATE: str = """
        你是医学领域的专业大学教授，现在需要你根据我传递给你的知识库内容构建一道选择题

        **输出要求:**

        - 我发给你的内容是相关需要生成的试题的知识点
        - 你需要确保你给的题目具有逻辑性且有唯一正确答案
        - 你需要返回题目、选项、答案、解析
        - 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
        - 按照题目题型特点生产试题，特点为：{qtype}

        **知识库内容:**
        {knowledge_description}

        **输出案例（仅提供格式输出，不提供知识点参考）：**

        {case}

        """

    name: str = "questionGeneration"

    async def run(self, knowledge_description: str):
        qtype = [
            {
                "名称": "概念判断题",
                "特点": "针对基本概念的理解与记忆，要求考生判断对错或从多个选项中选择符合题干描述的正确答案。",
                "输出案例": {
                    "topic": "有关人体内控制系统中的调定点，错误的描述是？",
                    "options": {
                        "A": "调定点通过负反馈调节",
                        "B": "调定点是内环境稳定的标准值",
                        "C": "调定点不可调节",
                        "D": "调定点可受环境因素影响"
                    },
                    "answer": "C",
                    "parse": "调定点是一个通过反馈机制调节的标准值，通常不受外部因素直接改变，因此错误的描述是C选项。"
                }
            },
            {
                "名称": "机制分析题",
                "特点": "考察生理、生化、病理等机制或过程的理解。",
                "输出案例": {
                    "topic": "骨骼肌细胞横管膜L型钙通道激活后的生理效应是？",
                    "options": {
                        "A": "引起钙离子进入细胞，激活肌肉收缩",
                        "B": "抑制钙离子进入细胞，导致肌肉松弛",
                        "C": "通过促进钠离子进入激活收缩",
                        "D": "引起细胞膜去极化"
                    },
                    "answer": "A",
                    "parse": "L型钙通道激活后，会引起钙离子进入细胞，进一步激活肌肉收缩机制，A选项是正确的描述。"
                }
            },
            {
                "名称": "症状诊断题",
                "特点": "通过患者的症状、体征和实验室检查结果，考察考生的临床推理能力。",
                "输出案例": {
                    "topic": "23岁男性，发热、寒战，伴乏力和脾肿大，最可能的诊断是？",
                    "options": {
                        "A": "急性白血病",
                        "B": "肝炎",
                        "C": "感染性单核细胞增多症",
                        "D": "结核性肺炎"
                    },
                    "answer": "C",
                    "parse": "感染性单核细胞增多症常表现为发热、寒战、乏力、脾肿大等症状，最符合该患者的临床表现。"
                }
            },
            {
                "名称": "治疗与处理题",
                "特点": "关注疾病的治疗原则、首选药物或手术方式。",
                "输出案例": {
                    "topic": "急性前壁心肌梗死，急诊处理最正确的是？",
                    "options": {
                        "A": "立即进行冠脉介入治疗",
                        "B": "服用阿司匹林并观察",
                        "C": "仅进行静脉输液和氧疗",
                        "D": "进行胸部X光检查"
                    },
                    "answer": "A",
                    "parse": "急性前壁心肌梗死需要尽早进行冠脉介入治疗（PCI），以恢复血流，减轻心肌损伤，A选项是正确的处理方法。"
                }
            },
            {
                "名称": "综合型分析题",
                "特点": "涉及多学科内容，综合考察考生的知识应用能力。",
                "输出案例": {
                    "topic": "可通过激活酪氨酸激酶受体完成细胞信号转导的配体有？",
                    "options": {
                        "A": "胰岛素",
                        "B": "肾上腺素",
                        "C": "乙酰胆碱",
                        "D": "多巴胺"
                    },
                    "answer": "A",
                    "parse": "胰岛素是通过与酪氨酸激酶受体结合，激活其信号转导通路，从而调控细胞代谢的，A选项为正确答案。"
                }
            }
        ]
        # knowledge_description = parse_json(knowledge_description)
        q = random.choice(qtype)
        qtype = q['名称'] + ':' + q['特点']
        case = q['输出案例']
        prompt = self.PROMPT_TEMPLATE.format(knowledge_description=knowledge_description[-1], qtype=qtype, case=case)
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
