import json
import warnings

from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from tqdm import tqdm

warnings.filterwarnings("ignore")


def revise_format(json_data):
    if "relations" in json_data and isinstance(json_data["relations"], str):
        json_data["relation"] = json_data.pop("relations")

    if "entitie" in json_data and isinstance(json_data["entitie"], str):
        json_data["entities"] = json_data.pop("entitie")

    # 检查 "knowledge" 字段
    if "knowledge" not in json_data or not isinstance(json_data["knowledge"], str):
        json_data['knowledge'] = ''

    # 检查 "entities" 字段
    if "entities" not in json_data or not isinstance(json_data["entities"], list):
        json_data['entities'] = []

    else:
        for index, entity in enumerate(json_data["entities"]):
            missing_keys = [key for key in ["entity", "type", "description"] if key not in entity]
            if missing_keys:
                for rel in json_data['entities']:
                    if '描述' in rel:
                        rel['description'] = rel.pop('描述')

    # 检查 "relation" 字段
    if "relation" not in json_data or not isinstance(json_data["relation"], list):
        json_data['relation'] = []
    else:
        for index, relation in enumerate(json_data["relation"]):
            missing_keys = [key for key in ["entity1", "relation", "entity2"] if key not in relation]
            if missing_keys:
                for rel in json_data['relation']:
                    if 'subject' in rel:
                        rel['entity1'] = rel.pop('subject')
                    if 'predicate' in rel:
                        rel['relation'] = rel.pop('predicate')
                    if 'object' in rel:
                        rel['entity2'] = rel.pop('object')
                    if 'type' in rel:
                        rel['relation'] = rel.pop('type')
                    if 'relationship' in rel:
                        rel['relation'] = rel.pop('relationship')

    return json_data


def check_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"File '{file_path}' is not a valid list of JSON objects.")
            return

        # 验证每个 JSON 对象的格式
        for idx, json_object in enumerate(data):
            data[idx] = revise_format(json_object)

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    return data


def validate_json_format(json_data):
    errors = []

    # 检查 "knowledge" 字段
    if "knowledge" not in json_data or not isinstance(json_data["knowledge"], str):
        errors.append(("knowledge", "Missing or invalid 'knowledge' field"))

    # 检查 "entities" 字段
    if "entities" not in json_data or not isinstance(json_data["entities"], list):
        errors.append(("entities", "Missing or invalid 'entities' field"))
    else:
        for index, entity in enumerate(json_data["entities"]):
            missing_keys = [key for key in ["entity", "type", "description"] if key not in entity]
            if missing_keys:
                errors.append((f"entities[{index}]", f"Missing keys: {', '.join(missing_keys)}"))

    # 检查 "relation" 字段
    if "relation" not in json_data or not isinstance(json_data["relation"], list):
        errors.append(("relation", "Missing or invalid 'relation' field"))
    else:
        for index, relation in enumerate(json_data["relation"]):
            missing_keys = [key for key in ["entity1", "relation", "entity2"] if key not in relation]
            if missing_keys:
                errors.append((f"relation[{index}]", f"Missing keys: {', '.join(missing_keys)}"))

    return errors


systemContent = r"""任务：  
从给定的文本中自动抽取出实体

模型参与的角色：  
你将作为一个医学知识图谱的构建助手，负责进行我的实体的命名的修改。

要求：
1. 识别出dict中的主要实体，对命名错误的进行修正
2. 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
3. 最终输出应包含一个包含多个实体的dict。

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

prompt_template = ChatPromptTemplate.from_messages(
    [("system", systemContent), ("user", "{text}")]
)

model = Ollama(model="qwen2.5", temperature=0.0)
parser = JsonOutputParser()
chain = prompt_template | model | parser

# 文件路径
json_file_path = "../data/graph.json"

# 检查 JSON 文件
data = check_json_file(json_file_path)

for idx, json_object in tqdm(enumerate(data)):
    error = validate_json_format(json_object)
    if error:
        data[idx] = chain.invoke({'text': json_object})

data = [json_object for json_object in data if not validate_json_format(json_object)]

for idx, json_object in enumerate(data):
    if validate_json_format(json_object):
        print(f'{idx}: {validate_json_format(json_object)}')

with open('../data/graph.json', 'w', encoding='utf-8') as json_file:
    json.dump(data, json_file, ensure_ascii=False, indent=4)
