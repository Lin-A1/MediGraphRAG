import json
import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yaml
from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from tqdm import tqdm

warnings.filterwarnings("ignore")


class KnowledgeProcessor:
    def __init__(self, knowledge_file, graph_file, model_name="qwen2.5", temperature=0.0, max_workers=None):
        self.knowledge_file = knowledge_file
        self.graph_file = graph_file
        self.model_name = model_name
        self.temperature = temperature
        self.max_workers = max_workers or (os.cpu_count() // 2)

        self.data = self.load_knowledge()
        self.chain = self.setup_chain()
        self.summary_chain = self.setup_summary_chain()
        self.responses = self.load_graph()

    def load_knowledge(self):
        data = pd.read_json(self.knowledge_file)
        return data.drop_duplicates(keep='last', ignore_index=True)

    def setup_chain(self):
        system_content = r"""任务：  
        从给定的文本中自动抽取出实体
        
        模型参与的角色：  
        你将作为一个医学知识图谱的构建助手，负责从医学文本中识别和提取重要实体，并将提取结果以结构化的形式呈现。
        
        要求：
        1. 识别出文本中的主要实体，并对实体分类。
        2. 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
        3. 注意只需要提取与医疗相关实体，不需要提取太过于泛的实体，比如`人群`，要求如下：
        
        - 实体字段
        疾病（Disease）：疾病名称、疾病编码（如ICD-10）、描述、分类（如慢性病、传染病等）。
        药物（Drug）：药物名称、剂量、适应症、禁忌、常见副作用。
        症状（Symptom）：症状名称、描述、严重程度、出现频率。
        治疗方法（Treatment）：治疗方案、方法（如手术、药物治疗）、疗效、适应症。
        检查项目（Test）：检查名称、目的、结果范围、相关疾病。
        
        4. 最终输出应包含一个包含多个实体的dict。
        
        输出案例：  
        给定文本：  
        "胰岛素是调节血糖水平的重要激素，胰腺是其主要分泌腺体。"
        
        **系统应输出以下字典格式：**
        {{
          "knowledge": "胰岛素是调节血糖水平的重要激素，胰腺是其主要分泌腺体。",
          "entities": [
            {{
              "entity": "胰岛素",
              "type": "激素",
              "description": "调节血糖水平的激素"
            }},
            {{
              "entity": "血糖水平",
              "type": "生理指标",
              "description": "血液中的葡萄糖含量"
            }},
            {{
              "entity": "胰腺",
              "type": "器官",
              "description": "分泌胰岛素的腺体"
            }}
          ]
        }}

        """
        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_content), ("user", "{text}")]
        )
        model = Ollama(model=self.model_name, temperature=self.temperature)
        parser = JsonOutputParser()
        return prompt_template | model | parser

    def setup_summary_chain(self):
        summary_content = r"""任务： 从给定的文本中自动抽取出实体及其相互关系，构建知识图谱，并将提取结果以结构化的形式呈现

        要求：
        1. `relation`中的实体，应仅从提供的实体中提取。
        2. 从文本中提取实体之间的关系，明确并准确描述关系类型。
        3. 输出应采用字典格式，实体和关系以 `dict` 表示，关系以三元组形式。
        4. 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
        5. 注意只需要提取与医疗相关的实体关系，要求如下：
        
        - 关系字段
        疾病与症状：哪些症状与哪些疾病相关联（例如，咳嗽与肺炎）。
        疾病与药物：哪些药物用于治疗特定疾病（例如，阿莫西林用于治疗细菌感染）。
        症状与检查项目：某些症状需要进行哪些检查（例如，咳嗽需要进行胸部X光）。
        药物与副作用：药物可能引起的副作用（例如，阿司匹林可能导致胃肠不适）。
        
        关系应当包括但不限于以下：["导致症状", "伴随症状", "治疗方法", "疗效", "风险因素", "保护因素", "检查方法", "检查指标", "高发人群", "易感人群", "药物治疗", "药物副作用", "病理表现", "生物标志物", "发生率", "预后因素", "病因", "传播途径", "预防措施", "生活方式影响", "相关疾病", "诊断标准", "自然病程", "临床表现", "并发症", "危险信号", "遗传因素", "环境因素", "生活方式干预", "治疗费用", "治疗反应", "康复措施", "心理影响", "社会影响"]
        
        
        6. 最终输出应包含一个包含多个关系的列表，以便用于知识图谱构建。
        
        输出案例：  
        
        **系统应输出以下字典格式：**
        
        {{
          "knowledge": "胰岛素是调节血糖水平的重要激素，胰腺是其主要分泌腺体。",
          "entities": [
            {{
              "entity": "胰岛素",
              "type": "激素",
              "description": "调节血糖水平的激素"
            }},
            {{
              "entity": "血糖水平",
              "type": "生理指标",
              "description": "血液中的葡萄糖含量"
            }},
            {{
              "entity": "胰腺",
              "type": "器官",
              "description": "分泌胰岛素的腺体"
            }}
          ],
          "relation": [
            {{
              "entity1": "胰岛素",
              "relation": "调节",
              "entity2": "血糖水平"
            }},
            {{
              "entity1": "胰岛素",
              "relation": "主要分泌腺体",
              "entity2": "胰腺"
            }}
          ]
        }}

        """
        summary_template = ChatPromptTemplate.from_messages(
            [("system", summary_content), ("user", "{text}")]
        )
        summary_model = Ollama(model=self.model_name, temperature=self.temperature)
        parser = JsonOutputParser()
        return summary_template | summary_model | parser

    def load_graph(self):
        if not os.path.exists(self.graph_file):
            with open(self.graph_file, 'w') as f:
                json.dump([], f)

        with open(self.graph_file, 'r') as f:
            return json.load(f)

    def process_knowledge(self, text):
        time = 0
        while True:
            try:
                entitys = self.chain.invoke({"text": text})  # 调用实体识别链
                response = self.summary_chain.invoke({"text": entitys})  # 调用摘要链
                if isinstance(response, dict) and response:
                    return response  # 返回响应
                else:
                    return None  # 如果没有响应，返回 None
            except Exception as e:
                time += 1
                if time > 5:
                    print(f"处理失败: {text}, 错误: {e}")
                    return None

    def process_all(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.process_knowledge, i): i for i in self.data['knowledge']}

            for future in tqdm(as_completed(futures), total=len(futures)):
                result = future.result()
                if result is not None:
                    self.responses.append(result)  # 添加响应
                    # 立即写入文件
                    with open(self.graph_file, 'w') as f:
                        json.dump(self.responses, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":

    # 读取 YAML 配置文件
    with open('../config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # 解析环境变量
    save_dir = os.path.expandvars(config['save']['dir'])


    processor = KnowledgeProcessor(
        knowledge_file='../../data/knowledge/knowledge3.json',
        graph_file='../../data/graph/graph.json'
    )
    processor.process_all()
