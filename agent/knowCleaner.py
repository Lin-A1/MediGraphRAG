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
        数据：{knowledge}
        你是一个医学知识处理系统，任务是从给定的医学数据中提取和构建结构化的知识点，要求如下：

        1. **数据清洗与标准化**：
           - 输入：包含医学实体和相关描述的原始数据（如疾病、症状、治疗、病因等）。
           - 输出：清洗后的医学数据，标准化的实体及描述。

        2. **知识点提取**：
           - 从输入的数据中提取出有意义的**知识点**，如病因、症状、并发症、治疗方法等。
           - 标注每个知识点的类别，如“症状”、“病因”、“治疗”等。

        3. **数据优化**：
           - 确保数据中不包含冗余或不相关的信息。
           - 确保每个知识点都能准确地反映医学领域的真实情况。

        4. **结构化输出**：
           - 输出一个字典数据结构，其中键是 `knowledge`，值为一个包含相关知识点的列表。
           - 示例输出格式：
             ```json
             {{
               "knowledge": [
                 "尿毒症是一种由于慢性肾功能衰竭导致的代谢性疾病",
                 "尿毒症的症状包括食欲丧失、恶心、呕吐、乏力等",
                 "尿毒症可能由多种病因引起，包括急性肾衰竭、慢性肾病等",
                 "尿毒症的治疗方法包括透析治疗、肾移植等"
               ]
             }}
             ```
        5. **输出结果**：
           - 你需要从输入数据中提取清晰且有意义的医学知识点，确保结构化且符合实际医学背景。
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
