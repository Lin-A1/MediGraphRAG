import warnings

import pandas as pd
from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

warnings.filterwarnings("ignore")

data = pd.read_json('../data//knowledge/knowledge3.json')
data = data.drop_duplicates(keep='last', ignore_index=True)

systemContent = r"""任务：  
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
    [("system", systemContent), ("user", "{text}")]
)

model = Ollama(model="qwen2.5", temperature=0.0)
parser = JsonOutputParser()
chain = prompt_template | model | parser

summaryContent = r"""任务： 从给定的文本中自动抽取出实体及其相互关系，构建知识图谱，并将提取结果以结构化的形式呈现

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
    [("system", summaryContent), ("user", "{text}")]
)

summarymodel = Ollama(model="qwen2.5", temperature=0.0)
summarychain = summary_template | summarymodel | parser


if not os.path.exists('../data/graph.json'):
    with open('../data/graph.json', 'w') as f:
        json.dump([], f)

with open('../data/graph.json', 'r') as f:
    responses = json.load(f)


def process_knowledge(i):
    time = 0
    while True:
        try:
            entitys = chain.invoke({"text": i})  # 调用实体识别链
            response = summarychain.invoke({"text": entitys})  # 调用摘要链
            if isinstance(response, dict):
                if response:
                    return response  # 返回响应
                else:
                    return None  # 如果没有响应，返回 None
        except Exception as e:
            time += 1
            if time > 5:
                print(f"处理失败: {i}, 错误: {e}")
                return None
            pass


def process_all(data, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_knowledge, i): i for i in data['knowledge']}

        for future in tqdm(as_completed(futures), total=len(futures)):
            result = future.result()
            if result is not None:
                responses.append(result)  # 添加响应

                # 立即写入文件
                with open('../data/graph.json', 'w') as f:
                    json.dump(responses, f, ensure_ascii=False, indent=4)


# 调用处理函数
process_all(data, max_workers=os.cpu_count() // 2)
