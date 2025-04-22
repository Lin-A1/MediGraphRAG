from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import os
from neo4j import GraphDatabase

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Neo4j配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

class GraphSearchRequest(BaseModel):
    keyword: str

class Node(BaseModel):
    name: str
    category: str
    value: Optional[int] = 1
    symbolSize: Optional[int] = 50
    color: Optional[str] = None

class Link(BaseModel):
    source: str
    target: str
    label: Optional[str] = None

class GraphResponse(BaseModel):
    nodes: List[Node]
    links: List[Link]

@app.post("/graph/search")
async def search_graph(request: GraphSearchRequest):
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # 查询与关键词相关的节点和关系
            query = """
            MATCH (n)-[r]-(m)
            WHERE n.name CONTAINS $keyword OR m.name CONTAINS $keyword
            RETURN DISTINCT n, r, m
            LIMIT 50
            """
            
            result = session.run(query, keyword=request.keyword)
            
            # 处理结果
            nodes = {}
            links = []
            
            for record in result:
                # 处理起始节点
                source_node = record["n"]
                if source_node.id not in nodes:
                    nodes[source_node.id] = Node(
                        name=source_node["name"],
                        category=list(source_node.labels)[0],
                        color=get_node_color(list(source_node.labels)[0])
                    )
                
                # 处理目标节点
                target_node = record["m"]
                if target_node.id not in nodes:
                    nodes[target_node.id] = Node(
                        name=target_node["name"],
                        category=list(target_node.labels)[0],
                        color=get_node_color(list(target_node.labels)[0])
                    )
                
                # 处理关系
                relationship = record["r"]
                links.append(Link(
                    source=source_node["name"],
                    target=target_node["name"],
                    label=relationship.type
                ))
            
            driver.close()
            
            return GraphResponse(
                nodes=list(nodes.values()),
                links=links
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_node_color(label):
    colors = {
        "知识点": "#1976d2",
        "疾病": "#ef4444",
        "症状": "#22c55e",
        "药物": "#f59e0b"
    }
    return colors.get(label, "#64748b")

@app.get("/health")
async def health_check():
    return {"status": "ok"} 