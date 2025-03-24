import os
import faiss
import numpy as np
import yaml
from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .Rerank import Reranker
from .Embedding import LoadModel, encode_text
from .Neo4jEntityFetcher import Neo4jEntityFetcher


class MedicalKnowledgeFetcher:
    def __init__(self, config_path='config/config.yaml', faiss_index_path=None, metadata_path=None,
                 neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="password"):
        # 加载配置文件
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)

        # 解析配置文件中的路径
        self.base_dir = self.config['base']['dir']
        self.faiss_index_path = faiss_index_path or os.path.join(self.base_dir,
                                                                 self.config['faiss']['faiss_index_path'])
        self.metadata_path = metadata_path or os.path.join(self.base_dir, self.config['faiss']['metadata_path'])

        # 加载FAISS索引和ID
        self.loaded_index = faiss.read_index(self.faiss_index_path)
        self.loaded_ids = np.load(self.metadata_path)

        # 初始化Neo4j连接
        self.fetcher = Neo4jEntityFetcher(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)

        # 初始化模型
        self.model, self.tokenizer = LoadModel()

    def query_knowledge(self, query_text, top_k=3):
        query_vector = encode_text(self.model, self.tokenizer, query_text)

        # 执行FAISS查询
        D, I = self.loaded_index.search(np.array(query_vector, dtype=np.float32), k=30)

        knowledges = []
        for i in I[0]:
            entity_id = self.loaded_ids[i]
            entity = self.fetcher.get_entity_by_id(entity_id)
            knowledge = self._extract_entity_knowledge(entity)
            knowledges.append(knowledge)
        reranker = Reranker()
        knowledges = reranker.rerank(query_text, knowledges, top_k)
        knowledges = [item[0] for item in knowledges]
        return knowledges[::-1]

    def _extract_entity_knowledge(self, entity):
        knowledge = ''
        knowledge += entity[0]['properties']['name'] + '\n\n'
        if entity[0]['labels'][0] == 'entity':
            ent = self.fetcher.get_entities_by_entities_id(entity[0]['id'])
            if len(ent) > 0:
                key = ent[0]['key']
            else:
                key = ''
            type, description, know, relation = '', '', [], []
            for e in ent:
                if e['relationship']['type'] == 'type' and type == '':
                    type = e['properties']
                if e['relationship']['type'] == 'description' and description == '':
                    description = e['properties']
                if e['relationship']['type'] == 'knowledge':
                    know.append(e['properties'])
                if e['relationship']['type'] == 'relation':
                    relation.append((e['key'], e['relationship']['properties']['relation'], e['properties']))
            knowledge += f'\n{key, type, description},\n相关知识点：{know},\n相关实体：{relation}\n'

        if entity[0]['labels'][0] == 'knowledge':
            entities = self.fetcher.get_entities_by_knowledge_id(entity[0]['id'])
            types, descriptions = [], []
            for i in entities:
                ent = self.fetcher.get_entities_by_entities_id(i['id'])
                type, description = '', ''
                key = ent[0]['key']
                for e in ent:
                    if e['relationship']['type'] == 'type' and type == '':
                        type = e['properties']
                    if e['relationship']['type'] == 'description' and description == '':
                        description = e['properties']
                knowledge += f'{(key, description, type)}'
        return knowledge

    def describe_knowledge(self, knowledge):
        system_content = """
        你是医学领域的专业大学教授，现在需要你根据我给你的数据描述出这段数据表达的知识点

        **输出要求:**

        - 我发给你的内容中包括我需要描述的知识点、以及与他有关的实体与实体的解释
        - 我给你的内容中的描述、类型、相关知识点、以及与他有关的实体可能有多种，你需要完整的描述
        - 你仅需要描述相关内容，不需要额外拓展
        - 尽量以严谨的科学口吻描述完整的描述
        - 返回内容为一段话即可，不需要复杂的格式
        """

        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_content), ("user", "{text}")]
        )

        model = Ollama(model="qwen2.5", temperature=0.0)
        parser = StrOutputParser()
        chain = prompt_template | model | parser

        response = chain.invoke({"text": knowledge})
        return response

    def generate_multiple_choice_question(self, knowledge_description):
        system_content = """
        你是医学领域的专业大学教授，现在需要你根据我传递给你的知识点构建一道选择题

        **输出要求:**

        - 我发给你的内容是相关需要生成的试题的知识点
        - 你需要确保你给的题目具有逻辑性且有唯一正确答案
        - 你需要返回题目、选项、答案、解析
        - 题目的表达形式可以有多种，比如直接提问法、填空法、是非判断法、因果推理法、选择特定选项法、定义法和应用场景法。
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
            }},
            "answer":"C",
            "parse":"血液溢出血管后形成血肿，大量的X线吸收系数明显高于脑实质的血红蛋白积聚在一起，CT图像上表现为高密度病灶，CT值多高于60Hu。"
        }}
        """

        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_content), ("user", "{text}")]
        )

        model = Ollama(model="qwen2.5", temperature=0.3)
        parser = JsonOutputParser()
        chain = prompt_template | model | parser

        response = chain.invoke({"text": '', 'knowledge_description': knowledge_description})
        return response


if __name__ == "__main__":
    fetcher = MedicalKnowledgeFetcher()

    # 查询糖尿病相关知识
    knowledges = fetcher.query_knowledge("尿毒症")

    knowlist = []

    # 生成知识描述并基于描述生成选择题
    for knowledge in knowledges:
        knowledge_description = fetcher.describe_knowledge(knowledge)
        knowlist.append(knowledge_description)
        print("生成的知识描述:", knowledge_description)

    question = fetcher.generate_multiple_choice_question(knowlist)
    print("生成的选择题:", question)
