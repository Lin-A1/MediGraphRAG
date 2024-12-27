import re

from metagpt.actions import Action, UserRequirement
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message


def parse_json(rsp):
    pattern = r"```json(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    json = match.group(1) if match else rsp
    return json


class knowClean(Action):
    PROMPT_TEMPLATE: str = """
        你是一个医学知识处理系统，任务是从给定的医学数据中提取和构建结构化的知识图谱。以下是你的工作流程：
        
        1. **数据清洗与标准化**：
           - 输入：包含医学实体和相关描述的原始数据（如疾病、症状、治疗、病因等）。
           - 输出：清洗后的医学数据，标准化的实体及描述。
        
        2. **知识点提取**：
           - 从输入的数据中提取出有意义的**知识点**，如病因、症状、并发症、治疗方法等。
           - 标注每个知识点的类别，如“症状”、“病因”、“治疗”等。
        
        3. **实体关系抽取**：
           - 识别数据中的**实体**（如“尿毒症”、“缩窄性心包炎”）和它们之间的**关系**（如“病因”、“引起症状”等）。
           - 构建实体之间的关联关系，例如：“尿毒症”引起“缩窄性心包炎”。
           - 为每对实体之间建立关系并提供简要描述。
        
        4. **结构化输出**：
           - 输出一个结构化的**实体关系图谱**，图谱中包含实体、关系及其描述，确保知识点之间的联系明确且完整。
           - 示例输出格式：
             ```json
             {{
               "疾病": "尿毒症",
               "症状": ["慢性肾衰竭的一种表现形式", "可能引起心包病变"],
               "病因": ["缩窄性心包炎", "结核", "化脓等感染性疾病"],
               "相关知识点": [
                 "缩窄性心包炎是由各种原因引起的心包增厚、粘连...",
                 "急进性肾小球肾炎的特点包括迅速进展至尿毒症..."
               ],
               "实体关系": [
                 {{
                   "实体1": "尿毒症",
                   "关系": "病因",
                   "实体2": "缩窄性心包炎"
                 }},
                 {{
                   "实体1": "尿毒症",
                   "关系": "引起症状",
                   "实体2": "心包病变"
                 }}
               ]
             }}
            ```

        5. **数据优化**：
           - 确保数据中不包含冗余或不相关的信息。
           - 确保每个实体和知识点都能准确地反映医学领域的真实情况。
        
        要求：
        - 处理过程中要避免信息丢失或误分类。
        - 确保结构化数据的质量高，能够为后续的试题生成模型提供准确的背景知识。
        
        数据：{knowledge}

        """

    name: str = "knowClean"

    async def run(self, knowledge: str):
        prompt = self.PROMPT_TEMPLATE.format(knowledge=knowledge)
        rsp = await self._aask(prompt)
        text = parse_json(rsp)
        return text


class knowCleaner(Role):
    name: str = "Knowledge cleaner"
    profile: str = "进行图谱提取数据的清洗与增强"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([knowClean])
        self._watch([UserRequirement])
