import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import faiss
import numpy as np
import pandas as pd
import yaml
from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from neo4j import GraphDatabase
from tqdm import tqdm

from Embedding import *
from Neo4jEntityFetcher import Neo4jEntityFetcher

warnings.filterwarnings("ignore")


class GraphBuilder:
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

            for future in tqdm(as_completed(futures), total=len(futures), desc="Building Graph"):
                result = future.result()
                if result is not None:
                    self.responses.append(result)  # 添加响应
                    # 立即写入文件
                    with open(self.graph_file, 'w') as f:
                        json.dump(self.responses, f, ensure_ascii=False, indent=4)


class GraphNormalizer:
    def __init__(self, json_file_path, model_name="qwen2.5", temperature=0.0):
        self.json_file_path = json_file_path
        self.model_name = model_name
        self.temperature = temperature
        self.chain = self.setup_chain()

    def setup_chain(self):
        system_content = r"""任务：  
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
            [("system", system_content), ("user", "{text}")]
        )
        model = Ollama(model=self.model_name, temperature=self.temperature)
        parser = JsonOutputParser()
        return prompt_template | model | parser

    @staticmethod
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

    @staticmethod
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

    def check_json_file(self):
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                print(f"File '{self.json_file_path}' is not a valid list of JSON objects.")
                return

            # 验证每个 JSON 对象的格式
            for idx, json_object in enumerate(data):
                data[idx] = self.revise_format(json_object)

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

        return data

    def process_json_file(self):
        data = self.check_json_file()
        for idx, json_object in tqdm(enumerate(data), desc="Normalizer Graph"):
            error = self.validate_json_format(json_object)
            if error:
                data[idx] = self.chain.invoke({'text': json_object})

        data = [json_object for json_object in data if not self.validate_json_format(json_object)]

        for idx, json_object in enumerate(data):
            if self.validate_json_format(json_object):
                print(f'{idx}: {self.validate_json_format(json_object)}')

        with open(self.json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)


class Neo4jKnowledgeGraph:
    def __init__(self, uri, user, password, json_file_path):
        self.uri = uri
        self.user = user
        self.password = password
        self.json_file_path = json_file_path
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.session = self.driver.session()
        self.data = self.load_data()

    def load_data(self):
        """加载JSON数据"""
        with open(self.json_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def close(self):
        """关闭Neo4j连接"""
        self.session.close()
        self.driver.close()

    def create_node(self, entity_name, entity_type=None):
        """创建节点"""
        for _ in range(3):
            try:
                if entity_type:
                    query = f"MERGE (n:`{entity_type}` {{name: $name}})"
                else:
                    query = "MERGE (n {name: $name})"
                self.session.run(query, name=entity_name)
                break
            except:
                time.sleep(2)

    def create_relationship(self, entity1_name, relation_type, entity2_name, properties=None):
        """创建关系"""
        for _ in range(3):
            try:
                if properties:
                    props = ', '.join([f"{key}: ${key}" for key in properties.keys()])
                    query = f"""
                    MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                    MERGE (a)-[:`{relation_type}` {{{props}}}]->(b)
                    """
                else:
                    query = f"""
                    MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                    MERGE (a)-[:`{relation_type}`]->(b)
                    """
                self.session.run(query, entity1_name=entity1_name, entity2_name=entity2_name, **(properties or {}))
                break
            except:
                time.sleep(2)

    def process_data(self):
        """处理数据并将其添加到Neo4j"""
        for d in tqdm(self.data, desc="up Neo4j"):
            knowledge = f"{d['knowledge']}"
            entities = d['entities']
            relation = d['relation']

            # 处理知识节点
            if knowledge != '':
                self.create_node(entity_name=knowledge, entity_type="knowledge")

            # 处理实体节点
            for entity in entities:
                entity_name = f"{entity['entity']}"
                entity_type = f"{entity['type']}"
                description = f"{entity['description']}"

                self.create_node(entity_name=entity_name, entity_type='entity')
                self.create_node(entity_name=description, entity_type='description')
                self.create_node(entity_name=entity_type, entity_type='type')

                # 创建关系
                if entity_name and description:
                    self.create_relationship(entity1_name=entity_name, relation_type='description',
                                             entity2_name=description)
                if entity_name and entity_type:
                    self.create_relationship(entity1_name=entity_name, relation_type='type', entity2_name=entity_type)
                if knowledge != '' and entity_name and knowledge:
                    self.create_relationship(entity1_name=entity_name, relation_type='knowledge',
                                             entity2_name=knowledge)

            # 处理关系数据
            for rela in relation:
                entity1 = f"{rela['entity1']}"
                if isinstance(rela['entity2'], list):
                    entity2 = [f"{item}" for item in rela['entity2']]
                else:
                    entity2 = f"{rela['entity2']}"

                self.create_node(entity_name=entity1, entity_type='entity')

                # 处理多对多关系
                if isinstance(rela['entity1'], list):
                    for e1 in rela['entity1']:
                        self.create_node(entity_name=e1, entity_type='entity')
                        if knowledge != '':
                            self.create_relationship(entity1_name=e1, relation_type='knowledge', entity2_name=knowledge)

                        if isinstance(rela['entity2'], list):
                            for e2 in rela['entity2']:
                                self.create_node(entity_name=e2, entity_type='entity')
                                self.create_relationship(entity1_name=e1, relation_type='relation',
                                                         entity2_name=f"{e2}",
                                                         properties={'relation': rela['relation']})
                                if knowledge != '':
                                    self.create_relationship(entity1_name=e2, relation_type='knowledge',
                                                             entity2_name=knowledge)
                        else:
                            self.create_node(entity_name=entity2, entity_type='entity')
                            self.create_relationship(entity1_name=e1, relation_type='relation', entity2_name=entity2,
                                                     properties={'relation': rela['relation']})
                            if knowledge != '':
                                self.create_relationship(entity1_name=entity2, relation_type='knowledge',
                                                         entity2_name=knowledge)
                else:
                    self.create_node(entity_name=entity1, entity_type='entity')
                    if knowledge != '':
                        self.create_relationship(entity1_name=entity1, relation_type='knowledge',
                                                 entity2_name=knowledge)

                    if isinstance(rela['entity2'], list):
                        for e2 in rela['entity2']:
                            self.create_node(entity_name=e2, entity_type='entity')
                            self.create_relationship(entity1_name=entity1, relation_type='relation',
                                                     entity2_name=f"{e2}", properties={'relation': rela['relation']})
                            if knowledge != '':
                                self.create_relationship(entity1_name=e2, relation_type='knowledge',
                                                         entity2_name=knowledge)
                    else:
                        self.create_node(entity_name=entity2, entity_type='entity')
                        self.create_relationship(entity1_name=entity1, relation_type='relation', entity2_name=entity2,
                                                 properties={'relation': rela['relation']})
                        if knowledge != '':
                            self.create_relationship(entity1_name=entity2, relation_type='knowledge',
                                                     entity2_name=knowledge)

    def execute(self):
        """执行主任务"""
        self.process_data()
        self.close()


class Neo4jFAISSIndexer:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, model, tokenizer, batch_size=32):
        # Neo4j配置
        self.uri = neo4j_uri
        self.user = neo4j_user
        self.password = neo4j_password

        # 初始化Fetch对象
        self.fetcher = Neo4jEntityFetcher(self.uri, self.user, self.password)

        # Embedding模型
        self.model = model
        self.tokenizer = tokenizer

        # 批量大小和保存路径
        with open('../config/config.yaml', 'r') as file:
            config = yaml.safe_load(file)

        # 解析环境变量
        base_dir = config['base']['dir']
        faiss_index_path = os.path.join(base_dir, config['faiss']['faiss_index_path'])
        metadata_path = os.path.join(base_dir, config['faiss']['metadata_path'])

        self.batch_size = batch_size
        self.faiss_index_path = faiss_index_path
        self.metadata_path = metadata_path

        # 加载实体数据
        self.knowledge_entities = self._fetch_knowledge_entities()
        self.texts = [i['properties']['name'] for i in self.knowledge_entities]
        self.ids = [i['id'] for i in self.knowledge_entities]

        # 计算文本嵌入
        self.embeddings = self._generate_embeddings()

    def _fetch_knowledge_entities(self):
        """从Neo4j中获取知识实体"""
        knowledge_entities = self.fetcher.get_entities_by_label("knowledge")
        knowledge_entities.extend(self.fetcher.get_entities_by_label("entity"))
        return knowledge_entities

    def _generate_embeddings(self):
        """生成文本的嵌入"""
        embeddings = []
        for i in tqdm(range(0, len(self.texts), self.batch_size), desc="generate embeddings"):
            batch_texts = self.texts[i:i + self.batch_size]
            batch_embeddings = encode_text(self.model, self.tokenizer, batch_texts)
            embeddings.extend(batch_embeddings)
        return np.array(embeddings, dtype=np.float32)

    def create_faiss_index(self):
        """创建FAISS索引"""
        dim = self.embeddings.shape[1]  # 嵌入的维度
        index = faiss.IndexFlatL2(dim)  # 使用L2距离度量
        index.add(self.embeddings)  # 添加嵌入数据
        faiss.write_index(index, self.faiss_index_path)  # 写入FAISS索引文件
        np.save(self.metadata_path, self.ids)  # 保存对应的元数据
        print(f"FAISS索引已保存到 {self.faiss_index_path}")
        print(f"元数据已保存到 {self.metadata_path}")

    def load_faiss_index(self):
        """加载FAISS索引"""
        self.index = faiss.read_index(self.faiss_index_path)
        self.ids = np.load(self.metadata_path)
        print(f"FAISS索引已加载，元数据加载完毕。")
        return self.index, self.ids

    def search(self, query, top_k=5):
        """进行FAISS搜索"""
        query_embedding = encode_text(self.model, self.tokenizer, [query])
        query_embedding = np.array(query_embedding, dtype=np.float32)

        # 使用FAISS进行查询
        distances, indices = self.index.search(query_embedding, top_k)

        # 获取相关的实体ID
        results = [(self.ids[i], distances[0][idx]) for idx, i in enumerate(indices[0])]
        return results


if __name__ == "__main__":
    # 读取 YAML 配置文件
    with open('../config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # 解析环境变量
    base_dir = config['base']['dir']
    save_dir = os.path.join(base_dir, config['save']['dir'])
    knowledge_dir = os.path.join(base_dir, config['knowledge']['dir'])
    graph_dir = os.path.join(save_dir, config['graph']['dir'])

    processor = GraphBuilder(
        knowledge_file=knowledge_dir,
        graph_file=graph_dir
    )
    processor.process_all()

    graphNormalizer = GraphNormalizer(json_file_path=graph_dir)
    graphNormalizer.process_json_file()

    uri = 'bolt://' + str(config['neo4j']['host']) + ':' + str(config['neo4j']['port'])
    user = config['neo4j']['user']
    password = config['neo4j']['password']

    # 创建 Neo4j 知识图谱实例并执行
    graph = Neo4jKnowledgeGraph(uri, user, password, graph_dir)
    graph.execute()

    # 初始化模型和分词器
    model, tokenizer = LoadModel()

    # 初始化Neo4jFAISSIndexer类
    indexer = Neo4jFAISSIndexer(
        neo4j_uri=uri,
        neo4j_user=user,
        neo4j_password=password,
        model=model,
        tokenizer=tokenizer
    )

    # 创建FAISS索引
    indexer.create_faiss_index()