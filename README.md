 # MediGraphRAG

------
![cover](https://github.com/Lin-A1/MediGraphRAG/blob/main/docx/images/cover.png?raw=true)

MediGraphRAG 项目旨在构建一个医疗知识图谱并基于此实现 RAG（Retrieval-Augmented Generation）方法，应用于医学试题的生成，提升医学领域的信息管理与应用效率。项目通过知识点抽取、关系提取和知识融合，解决大模型在生成过程中可能出现的幻觉问题，确保模型生成内容的准确性和可靠性。最终目标是为医学教育和实践提供一个动态、准确的知识支持系统。

<div align='center'>
     <p>
        <a href='https://github.com/Lin-A1/MediGraphRAG'><img src='https://img.shields.io/badge/Project-Page-Green'></a>
        <img src='https://img.shields.io/github/stars/Lin-A1/MediGraphRAG?color=green&style=social' />
     </p>
     <p>
        <img src="https://img.shields.io/badge/python-3.10-blue">
        <img src="https://img.shields.io/badge/ollama-available-blue">
    </p>
</div>


## 环境
- `ollama`:[https://ollama.com/download](https://ollama.com/download)
- `python`:`conda create -n med python=3.10`
- `qwen2.5:14b`:`ollama run qwen2.5`

```sh
# ollama
# ollama自行选择参数量大小，同时可以选择调用api，只需要在comfig上进行修改metagpt配置即可
# 同时留意agent/questionGenerator.py中有调用ollama模块进行试题生成的验证，可以将其注释掉，强行判断验证结果，
curl -fsSL https://ollama.com/install.sh | sh # unbutu
ollama run qwen2.5
ollama run glm4
ollama run deepseek-r1

# docker
docker pull neo4j:latest
docker run --name med-neo4j -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/test neo4j:latest

# model
cd model
git lfs install
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5
git clone https://huggingface.co/BAAI/bge-reranker-v2-m3

# python
conda create -n med python=3.10
conda activate med
cd MediGraphRAG
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia
pip install -r requirements.txt
```

## 数据来源

- `顶层数据`->`医学考试试题` :已经进行知识的抽取，存储在`data/knowledge`中
- `可信数据`->`医疗书籍`：https://github.com/scienceasdf/medical-books -> [data/medical-books]
- `嵌入模型`： https://huggingface.co/BAAI/bge-large-zh-v1.5 -> [model/bge-large-zh-v1.5]

## 快速开始
```bash
# 先构建好上面所描述环境

# 拉取项目
git clone git@github.com:Lin-A1/MediGraphRAG.git
cd MediGraphRAG

# 虚拟环境
conda activate med

# 创建neo4j知识图谱
cd utils
python GraphBuilder.py

# 进行检索生成（仅支持ollama）
cd ..
python utils/generate.py

# 使用智能体
python main.py

# 可视化页面
cd web/frontend
npm install

cd ../../
bash web/run.sh
```

构建流程可见[process.md](docx/process.md)

## 更新
```text
2025.03.13:
- 使用fastapi将检索流程封装为接口：bash api/run.sh
- 生成器与解释器使用模型拆解，分别使用deepseek-r1:32b与qwen2.5:32b

2025.03.24：
- 作者显卡换了，模型改用14b
- 引入rerank模型，在知识库调出知识点后进行一次重排序

2025.03.24：
- 开始使用api啦！（可以自己在config中选择ollama还是api）
- 在web目录下构建了web页面
```
---

### 知识库构建

#### 1. **知识点抽取**
使用`qwen2.5:14b`从医学试题中抽取考题知识点。清洗后数据存储在[knowledge.json](data/knowledge/knowledge.json)中。

#### 2. **关系抽取**
同样使用`qwen2.5:14b`从抽取的知识点中识别实体与关系。数据存储在[graph.json](data/knowledge/graph.json)中。模型抽取时需指定实体与关系类别，避免错误抽取。

#### 3. **Neo4j构建**
使用[Neo4jBuilder.py](docx/process/data/Neo4jBuilder.py)将知识图谱数据导入Neo4j图数据库，以支持高效检索。

---

### RAG流程

#### 1. **嵌入模型**
使用`bge-large-zh-v1.5`进行实体和知识点编码

#### 2. **Neo4j数据提取**
使用[Neo4jEntityFetcher.py](docx/process/rag/Neo4jEntityFetcher.py)从Neo4j提取实体，提供基于属性、标签等条件的查询接口。

#### 3. **FAISS索引生成**
通过[IndexBuild.py](docx/process/rag/IndexBuild.py)构建FAISS索引，用于快速匹配实体和知识点。

#### 4. **RAG工作流**
在[ragWorkflow.py](docx/process/rag/ragWorkflow.py)中，输入关键词，利用FAISS索引进行实体匹配，提取相关知识点，生成医学试题。


---

### 模型输出

模型根据抽取的知识点生成医学试题，并返回题目、选项、答案和解析。例如：

```json
{
  "topic": "糖尿病患者治疗过程中出现酮症酸中毒，应首选的治疗方法是",
  "options": {
    "A": "口服降糖药",
    "B": "静脉输注葡萄糖加胰岛素",
    "C": "口服补液盐",
    "D": "使用胰岛素泵"
  },
  "answer": "B",
  "parse": "酮症酸中毒是糖尿病急性并发症，需通过静脉输注葡萄糖和胰岛素来治疗。"
}
```

## Agent
>调用智能体使用的是metagpt架构，可以选择调用api，只需要在comfig上进行修改metagpt配置即可
> 
>同时留意agent/questionGenerator.py中有调用ollama模块进行试题生成的验证，可以将其注释掉，强行判断验证结果，

在上述数据准备的基础上，我们使用`metagpt`构建试题，启动脚本为[main.py](main.py),相关agent配置位于[agent](agent),其他脚本位于[utils](utils)

## 配置

>开发框架配置

| 类别         | 工具/框架名称      | 功能描述                                                     |
| ------------ | ------------------ | ------------------------------------------------------------ |
| 模型部署工具 | Ollama             | 轻量级大模型管理与部署工具，支持多平台适配和快速加载。       |
| 模型开发框架 | LangChain          | 模块化 NLP 开发框架，支持复杂任务建模与优化。                |
| 数据构建模型 | qwen2.5:14b        | 参数量 140 亿的语言模型，适用于文本生成与上下文理解任务。    |
| 智能体框架   | MetaGpt            | 多智能体协作框架，支持任务分解、角色分配和动态交互。         |
| 智能体模型   | DeepSeek-r1:32B    | 参数量 320 亿的高性能语言模型，具备卓越的推理与理解能力。    |
| 图数据库     | Neo4j              | 高效的关系型图数据库，适用于知识图谱构建与复杂网络分析。     |
| 向量检索引擎 | faiss              | 高性能相似性搜索库，用于语义搜索和大规模向量数据处理。       |
| 嵌入模型     | bge-large-zh-v1.5  | 中文专用嵌入模型，生成高质量语义向量，支持下游任务如分类与检索。 |
| 重排序模型   | bge-reranker-v2-m3 | 中文Reranker模型，将数据映射到高纬度向量进行数据重排序       |

>实验环境硬件资源配置

| 组件     | 规格参数                          | 技术特性                           |
| -------- | --------------------------------- | ---------------------------------- |
| 处理器   | Intel Core i7-12700KF (8P+4E/20T) | 基础频率3.6GHz，睿频5.0GHz         |
| 显卡     | NVIDIA RTX4090 (24GB  GDDR6X)     | CUDA核心16384，FP32算力82.6 TFLOPS |
| 内存     | DDR4-3592MHz 64GB双通道           | CL18时序，带宽57.5GB/s             |
| 存储系统 | SamsungSSD980PRO1TB  NVMe SSD ×2  | 顺序读7,000MB/s，写5,100MB/s       |
| 操作系统 | Ubuntu 22.04 LTS                  | Linux 5.15内核，CUDA 12.2驱动环境  |





