import re

from metagpt.actions import Action, UserRequirement
from metagpt.roles import Role


def parse_json(rsp):
    pattern = r"```json(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    json = match.group(1) if match else rsp
    return json


class knowClean(Action):
    PROMPT_TEMPLATE: str = """
        数据：{knowledge}
        你是一个医学知识处理系统，任务是从给定的医学数据中提取和构建结构化的知识点，并通过相关实体中的三元知识图谱信息去完善和补充，并总结全部知识点。请按照以下要求进行处理：
        
        1. **数据清洗与标准化**：
           - 输入：包含医学实体（如疾病、症状、治疗、病因等）及其相关描述的原始数据。
           - 清洗后的医学数据，标准化的实体及描述。确保实体名称一致、术语精确，去除冗余和无关信息。
        
        2. **知识点提取与扩展**：
           - 请基于你你的医学知识背景进行诊断生成
           - 从输入的医学实体信息中提取并构建有意义的**知识点**。这些知识点可以包括病因、症状、治疗方法、并发症等领域。
           - 利用相关实体中的**三元知识图谱**信息（例如：`(实体1, 关系, 实体2)`）来补充和完善已有的知识点，或是从中生成新的知识点。
             - 例如，从已知的三元关系`('肺炎链球菌', '导致症状', '铁锈色痰')`可以推导出新的知识点：“肺炎链球菌引起的肺炎常伴有铁锈色痰”。
           - 确保通过三元关系补充的知识点和从文本中提取的知识点保持一致，并标注每个知识点的类别，如“症状”、“病因”、“治疗方法”等。
        
        3. **数据优化**：
           - 确保提取的知识点没有冗余和无关信息，所有知识点都要有医学背景支持，避免模糊或重复的表述。
           - 在结合三元知识图谱信息时，确保新的知识点有充足的证据支持，并且不会引入误导性或不准确的信息。
        
        4. **结构化输出**：
           - 输出一个字典数据结构，其中键为 `knowledge`，值为一个包含相关知识点的列表，确保输出格式结构清晰且便于后续处理。
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
            - 提取清晰且有意义的医学知识点，确保这些知识点与相关医学实体（如病因、症状、治疗等）之间的关系正确，并且通过三元知识图谱信息得到了适当的扩展和补充。
            - 输出的结果应当结构化、准确，能够方便后续医学分析、推理或决策支持。
            - 请输出全部已知的知识点
            - 请严格按照示例输出格式进行输出
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
