import numpy as np
import faiss
from Embedding import *
from Neo4jEntityFetcher import Neo4jEntityFetcher

from langchain.memory import ConversationBufferMemory
from langchain_core.output_parsers import JsonOutputParser,StrOutputParser
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate

loaded_index = faiss.read_index('../../data/faiss_index/faiss_index.index')
loaded_ids = np.load('../../data/faiss_index/matedata.npy')

query_text = '糖尿病'
model, tokenizer = LoadModel()
query_vector = encode_text(model, tokenizer, query_text)

# 进行查询
D, I = loaded_index.search(np.array(query_vector, dtype=np.float32), k=3) 

print("距离:", D)  # 距离
print("索引:", I)  # 对应的索引
print("ID:", [loaded_ids[i] for i in I[0]])

systemContent = """
    你是医学领域的专业大学教授，现在需要你根据我给你的数据描述出这段数据表达的知识点

    **输出要求:**
    
    - 我发给你的内容中包括我需要描述的知识点、以及与他有关的实体与实体的解释
    - 我给你的内容中的描述、类型、相关知识点、以及与他有关的实体可能有多种，你需要完整的描述
    - 你仅需要描述相关内容，不需要额外拓展
    - 尽量以严谨的科学口吻描述完整的描述
    - 返回内容为一段话即可，不需要复杂的格式
"""


prompt_template = ChatPromptTemplate.from_messages(
    [("system", systemContent), ("user", "{text}")]
)

model = Ollama(model="qwen2.5",temperature=0.0)
parser = StrOutputParser()
chain =  prompt_template | model | parser

uri = "bolt://localhost:7687"  # Neo4j 数据库地址
user = "neo4j"  # Neo4j 用户名
password = "password"  # Neo4j 密码
fetcher = Neo4jEntityFetcher(uri, user, password)

knowledges = []
for i in I[0]:
    entity_id = loaded_ids[i]
    entity = fetcher.get_entity_by_id(entity_id)
    knowledge = ''
    knowledge += entity[0]['properties']['name'] + '\n\n'
    if entity[0]['labels'][0] == 'entity':
        ent = fetcher.get_entities_by_entities_id(entity[0]['id'])  # 实体相关信息
        type = ''
        description = ''
        key = ent[0]['key']
        know = []
        relation = []
        for e in ent:
            if e['relationship']['type'] == 'type' and type == '':
                type = e['properties']
            if e['relationship']['type'] == 'description' and description == '':
                description = e['properties']
            if e['relationship']['type'] == 'knowledge':
                know.append(e['properties'])
            if e['relationship']['type'] == 'relation':
                relation.append((e['key'],e['relationship']['properties']['relation'],e['properties']))
        knowledge += f'{key,type,description},\n相关知识点：{know},\n相关实体：{relation}'
    if entity[0]['labels'][0] == 'knowledge':
        entities = fetcher.get_entities_by_knowledge_id(entity[0]['id'])  # 获取知识点相关实体
        types = []
        description = []
        for i in entities:
            ent = fetcher.get_entities_by_entities_id(i['id'])  # 实体相关信息
            type = ''
            description = ''
            key = ent[0]['key']
            for e in ent:
                if e['relationship']['type'] == 'type' and type == '':
                    type = e['properties']
                if e['relationship']['type'] == 'description' and description == '':
                    description = e['properties']
            knowledge += f'{(key,description,type)}'
    
    response = chain.invoke({"text": knowledge})
    print(response,end='\n\n\n\n')
    knowledges.append(response)

# memory = ConversationBufferMemory(return_messages=True)

knowledge = ''
for i in I[0]:
    entity_id = loaded_ids[i]
    entity = fetcher.get_entity_by_id(entity_id)
    know = entity[0]['properties']['name']

    # memory.save_context({"input": know},{"output": "以上消息已加入知识库"})
    knowledge += f'{know}\n\n'

# memory.load_memory_variables({})

systemContent = """
    你是医学领域的专业大学教授，现在需要你根据我传递给你的知识点构建一道选择题

    **输出要求:**
    
    - 我发给你的内容是相关需要生成的试题的知识点
    - 你需要从我发给你的知识库中选择部分作为这道题目的主要考点
    - 你需要确保你给的题目具有逻辑性且有唯一正确答案
    - 你需要返回题目、选项、答案、解析
    - 题目的表达形式可以有多种
    - 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
    
    **知识库内容:**
    {knowledge}

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
    [("system", systemContent), ("user", "{text}")]
)

model = Ollama(model="qwen2.5",temperature=0.3)
parser = JsonOutputParser()
chain =  prompt_template | model | parser

for k in knowledges:
    response = chain.invoke({ "text": '','knowledge':k})
    print(response,end='\n\n')