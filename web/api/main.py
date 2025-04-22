from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import re
from metagpt.logs import logger
from metagpt.team import Team
import asyncio
from functools import lru_cache
from neo4j import GraphDatabase

from utils.generate import MedicalKnowledgeFetcher
from agent.knowCleaner import knowCleaner
from agent.questionGenerator import questionGenerator

# 忽略 DeprecationWarning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 初始化 FastAPI 应用
app = FastAPI(title="Medical Knowledge API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化知识获取器
fetcher = MedicalKnowledgeFetcher()

# Neo4j配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# 定义请求和响应模型
class KeywordRequest(BaseModel):
    keyword: str

class KeywordResponse(BaseModel):
    keywords: List[str]

class KnowledgeWithQuestionResponse(BaseModel):
    keyword: str
    related_keywords: List[str]
    knowledge: str
    cleaned_knowledge: List[str]
    question: Optional[Dict] = None

class GraphSearchRequest(BaseModel):
    keyword: str

class Node(BaseModel):
    name: str
    category: str
    value: Optional[int] = 1
    symbolSize: Optional[int] = 50
    color: Optional[str] = None
    isBaseNode: bool = False

class Link(BaseModel):
    source: str
    target: str
    label: Optional[str] = None

class GraphResponse(BaseModel):
    nodes: List[Node]
    links: List[Link]

# 从知识清洗结果中提取结构化的知识点列表
def extract_knowledge_list(raw_knowledge_text):
    logger.info("开始提取知识点列表...")
    # 正则表达式匹配 JSON 格式的知识点
    pattern = r'```json(.*?)```'
    matches = re.findall(pattern, raw_knowledge_text, re.DOTALL)
    
    if matches:
        logger.info(f"找到 {len(matches)} 个JSON块")
        # 第一个智能体（知识清洗）的输出通常在第一个JSON块
        try:
            knowledge_data = json.loads(matches[0].strip())
            if isinstance(knowledge_data, dict) and "knowledge" in knowledge_data:
                knowledge_list = knowledge_data["knowledge"]
                if isinstance(knowledge_list, list):
                    logger.info("成功提取知识点列表")
                    return knowledge_list
                else:
                    logger.warning("knowledge字段不是列表类型，转换为列表")
                    return [str(knowledge_list)]
        except json.JSONDecodeError as e:
            logger.error(f"知识点JSON解析错误: {e}")
    
    logger.warning("未找到结构化的知识点数据，将原始文本转换为列表")
    return [raw_knowledge_text]

# 从智能体输出中提取试题JSON
def extract_question_from_output(output_text):
    logger.info("开始提取试题JSON...")
    # 尝试匹配独立的JSON块（特别是在输出最后部分）
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, output_text, re.DOTALL)
    
    if matches:
        logger.info(f"找到 {len(matches)} 个JSON块")
        # 第二个智能体（试题生成）的输出通常在最后一个JSON块
        last_json = matches[-1].strip()
        try:
            question_data = json.loads(last_json)
            # 检查是否是试题格式
            if isinstance(question_data, dict):
                # 处理嵌套的questions数组格式
                if 'questions' in question_data and isinstance(question_data['questions'], list) and len(question_data['questions']) > 0:
                    logger.info("找到嵌套的questions数组，提取第一个问题")
                    first_question = question_data['questions'][0]
                    # 合并topic和question
                    if 'topic' in question_data:
                        first_question['topic'] = question_data['topic'] + '\n' + first_question.get('question', '')
                    return first_question
                # 处理直接试题格式
                elif ('topic' in question_data or 'question' in question_data) and 'options' in question_data:
                    logger.info("找到直接试题格式")
                    return question_data
                else:
                    logger.warning(f"JSON块格式不符合预期: {question_data.keys()}")
        except json.JSONDecodeError as e:
            logger.error(f"试题JSON解析失败: {e}")
    
    # 如果上述方法失败，尝试使用更宽松的正则表达式查找
    try:
        # 查找包含试题特征的JSON对象
        json_like = re.search(r'\{\s*"topic".*?\}|\{\s*"question".*?\}', output_text, re.DOTALL)
        if json_like:
            question_data = json.loads(json_like.group(0))
            if isinstance(question_data, dict) and (
                    'topic' in question_data or 
                    'question' in question_data
                ) and 'options' in question_data:
                logger.info("使用宽松模式成功提取到试题")
                return question_data
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"宽松模式提取失败: {e}")
    
    logger.error("未能从输出中提取有效的试题JSON")
    return None

# 标准化试题格式
def standardize_question_format(question_data):
    logger.info("开始标准化试题格式...")
    if not isinstance(question_data, dict):
        logger.error(f"试题数据格式不符合预期: {type(question_data)}")
        return None
    
    # 检查必要字段
    required_fields = {
        'topic': question_data.get('topic', question_data.get('question', '')),
        'options': question_data.get('options', {}),
        'answer': question_data.get('answer', ''),
        'parse': question_data.get('parse', question_data.get('analysis', 
                 question_data.get('explanation', '')))
    }
    
    # 验证必要字段
    if not required_fields['topic'] or not required_fields['options'] or not required_fields['answer']:
        logger.error(f"试题缺少必要字段: {required_fields}")
        return None
    
    logger.info("试题格式标准化成功")
    return required_fields

# 获取知识点和生成试题（一站式接口）
@app.post("/get-knowledge-and-question", response_model=KnowledgeWithQuestionResponse)
async def get_knowledge_and_question(request: KeywordRequest):
    try:
        logger.info(f"开始处理关键词: {request.keyword}")
        # 使用 FAISS 进行匹配和重排序
        knowledges = fetcher.query_knowledge(request.keyword)
        related_keywords = [k.split('\n')[0] for k in knowledges[:3] if '\n' in k]  # 提取前三个关键词
        raw_knowledge = request.keyword + '\n' + '\n'.join(knowledges)
        
        logger.info("初始化工作流...")
        # 初始化工作流，与根目录main.py保持一致
        team = Team()
        team.hire([
            knowCleaner(),
            questionGenerator(),
        ])
        team.invest(investment=1000.0)  # 设置投资金额
        
        # 运行项目
        logger.info("开始运行工作流...")
        team.run_project(raw_knowledge)
        result = await team.run(n_round=2)  # 设置轮次为2，与根目录main.py保持一致
        logger.info("开始提取知识清洗结果...")
        # 提取知识清洗结果
        cleaned_knowledge = extract_knowledge_list(result)
        if not cleaned_knowledge:
            logger.error("知识清洗结果为空")
            raise HTTPException(status_code=500, detail="知识清洗结果为空")
        
        logger.info("开始提取试题...")
        # 从工作流输出中提取试题JSON
        question = extract_question_from_output(result)
        if question:
            question = standardize_question_format(question)
        
        # 如果试题提取失败，尝试重试
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries and question is None:
            logger.warning(f"试题提取失败，尝试重新运行工作流 ({retry_count + 1}/{max_retries})")
            retry_count += 1
            
            # 重新创建工作流并运行
            team = Team()
            team.hire([
                knowCleaner(),
                questionGenerator(),
            ])
            team.invest(investment=1000.0)
            team.run_project(raw_knowledge)
            result = await team.run(n_round=2)
            
            # 重新提取试题
            question = extract_question_from_output(result)
            if question:
                question = standardize_question_format(question)
            
            if question is None:
                await asyncio.sleep(1)  # 添加延迟避免过快重试
        
        if question is None:
            logger.error("试题提取失败，已达到最大重试次数")
            raise HTTPException(status_code=500, detail="试题提取失败")
        
        response = {
            "keyword": request.keyword,
            "related_keywords": related_keywords if related_keywords else [request.keyword],
            "knowledge": raw_knowledge,
            "cleaned_knowledge": cleaned_knowledge,  # 确保是列表类型
            "question": question
        }
        logger.info("处理完成，返回响应")
        return response
    except Exception as e:
        logger.error(f"获取知识和生成试题时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

def get_node_color(label):
    colors = {
        "知识点": "#1976d2",
        "疾病": "#1976d2",
        "症状": "#1976d2",
        "药物": "#1976d2"
    }
    return colors.get(label, "#1976d2")

@app.post("/graph/search")
async def search_graph(request: GraphSearchRequest):
    try:
        print(f"开始查询关键词: {request.keyword}")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # 首先检查数据库中是否有数据
            check_query = "MATCH (n) RETURN count(n) as count"
            count_result = session.run(check_query)
            total_nodes = count_result.single()["count"]
            print(f"数据库中总节点数: {total_nodes}")
            
            if total_nodes == 0:
                return GraphResponse(nodes=[], links=[])
            
            # 查询与关键词直接相关的节点和关系（基本节点）
            base_query = """
            MATCH (n)-[r]-(m)
            WHERE n.name CONTAINS $keyword OR m.name CONTAINS $keyword
            RETURN DISTINCT n, r, m
            LIMIT 10
            """
            
            base_result = session.run(base_query, keyword=request.keyword)
            
            # 处理基本节点结果
            nodes = {}
            links = []
            base_node_ids = set()
            
            for record in base_result:
                # 处理起始节点
                source_node = record["n"]
                if source_node.id not in nodes:
                    nodes[source_node.id] = Node(
                        name=source_node["name"],
                        category=list(source_node.labels)[0],
                        color=get_node_color(list(source_node.labels)[0]),
                        isBaseNode=True
                    )
                    base_node_ids.add(source_node.id)
                    print(f"添加基本节点: {source_node['name']} ({list(source_node.labels)[0]})")
                
                # 处理目标节点
                target_node = record["m"]
                if target_node.id not in nodes:
                    nodes[target_node.id] = Node(
                        name=target_node["name"],
                        category=list(target_node.labels)[0],
                        color=get_node_color(list(target_node.labels)[0]),
                        isBaseNode=True
                    )
                    base_node_ids.add(target_node.id)
                    print(f"添加基本节点: {target_node['name']} ({list(target_node.labels)[0]})")
                
                # 处理关系
                relationship = record["r"]
                links.append(Link(
                    source=source_node["name"],
                    target=target_node["name"],
                    label=relationship.type
                ))
                print(f"添加基本关系: {source_node['name']} -[{relationship.type}]-> {target_node['name']}")
            
            # 查询与基本节点相关的其他节点（相关节点）
            related_query = """
            MATCH (n)-[r]-(m)
            WHERE n.name CONTAINS $keyword OR m.name CONTAINS $keyword
            WITH n, r, m
            MATCH (n)-[r2]-(m2)
            WHERE m2.name CONTAINS $keyword OR n.name CONTAINS $keyword
            WITH n, r, m, r2, m2
            MATCH (m)-[r3]-(m3)
            WHERE m3.name CONTAINS $keyword OR m.name CONTAINS $keyword
            RETURN DISTINCT n, r, m, r2, m2, r3, m3
            LIMIT 100
            """
            
            related_result = session.run(related_query, keyword=request.keyword)
            
            # 处理相关节点结果
            for record in related_result:
                # 处理起始节点
                source_node = record["n"]
                if source_node.id not in nodes:
                    nodes[source_node.id] = Node(
                        name=source_node["name"],
                        category=list(source_node.labels)[0],
                        color=get_node_color(list(source_node.labels)[0]),
                        isBaseNode=False
                    )
                    print(f"添加相关节点: {source_node['name']} ({list(source_node.labels)[0]})")
                
                # 处理目标节点
                target_node = record["m"]
                if target_node.id not in nodes:
                    nodes[target_node.id] = Node(
                        name=target_node["name"],
                        category=list(target_node.labels)[0],
                        color=get_node_color(list(target_node.labels)[0]),
                        isBaseNode=False
                    )
                    print(f"添加相关节点: {target_node['name']} ({list(target_node.labels)[0]})")
                
                # 处理关系
                relationship = record["r"]
                links.append(Link(
                    source=source_node["name"],
                    target=target_node["name"],
                    label=relationship.type
                ))
                print(f"添加相关关系: {source_node['name']} -[{relationship.type}]-> {target_node['name']}")
                
                # 处理第二个目标节点（如果存在）
                if "m2" in record and record["m2"]:
                    target_node2 = record["m2"]
                    if target_node2.id not in nodes:
                        nodes[target_node2.id] = Node(
                            name=target_node2["name"],
                            category=list(target_node2.labels)[0],
                            color=get_node_color(list(target_node2.labels)[0]),
                            isBaseNode=False
                        )
                        print(f"添加相关节点: {target_node2['name']} ({list(target_node2.labels)[0]})")
                    
                    # 处理第二个关系
                    relationship2 = record["r2"]
                    links.append(Link(
                        source=source_node["name"],
                        target=target_node2["name"],
                        label=relationship2.type
                    ))
                    print(f"添加相关关系: {source_node['name']} -[{relationship2.type}]-> {target_node2['name']}")
                
                # 处理第三个目标节点（如果存在）
                if "m3" in record and record["m3"]:
                    target_node3 = record["m3"]
                    if target_node3.id not in nodes:
                        nodes[target_node3.id] = Node(
                            name=target_node3["name"],
                            category=list(target_node3.labels)[0],
                            color=get_node_color(list(target_node3.labels)[0]),
                            isBaseNode=False
                        )
                        print(f"添加相关节点: {target_node3['name']} ({list(target_node3.labels)[0]})")
                    
                    # 处理第三个关系
                    relationship3 = record["r3"]
                    links.append(Link(
                        source=target_node["name"],
                        target=target_node3["name"],
                        label=relationship3.type
                    ))
                    print(f"添加相关关系: {target_node['name']} -[{relationship3.type}]-> {target_node3['name']}")
            
            print(f"查询结果: {len(nodes)} 个节点, {len(links)} 个关系")
            
            driver.close()
            
            return GraphResponse(
                nodes=list(nodes.values()),
                links=links
            )
            
    except Exception as e:
        print(f"查询出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok"} 