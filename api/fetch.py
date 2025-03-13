from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from metagpt.logs import logger
from utils.generate import MedicalKnowledgeFetcher

# 忽略 DeprecationWarning
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# 初始化 FastAPI 应用
app = FastAPI()

# 初始化知识获取器
fetcher = MedicalKnowledgeFetcher()

# 定义请求模型
class KnowledgeRequest(BaseModel):
    keyword: str


# 定义响应模型
class KnowledgeResponse(BaseModel):
    keyword: str
    knowledge: str


# 查询每个关键词的相关知识
def fetch_knowledge_for_keywords(keyword: str) -> str:
    try:
        # 查询知识
        knowledges = fetcher.query_knowledge(keyword)
        # 拼接结果
        result = keyword + '\n' + '\n'.join(knowledges)
        return result
    except Exception as e:
        logger.error(f"Error fetching knowledge for keyword '{keyword}': {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch knowledge")


# 定义 API 接口
@app.post("/fetch-knowledge", response_model=KnowledgeResponse)
async def fetch_knowledge(request: KnowledgeRequest):
    """
    接收关键词并返回相关知识
    """
    keyword = request.keyword
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")

    # 获取知识
    knowledge = fetch_knowledge_for_keywords(keyword)

    # 返回响应
    return {"keyword": keyword, "knowledge": knowledge}


# 启动应用的入口（仅用于本地测试）
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)