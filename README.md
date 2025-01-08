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
curl -fsSL https://ollama.com/install.sh | sh # unbutu
ollama run qwen2.5

# docker
docker pull neo4j:latest
docker run --name med-neo4j -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/test neo4j:latest

# model
cd model
git lfs install
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5

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
cd dautilsta
python GraphBuilder.py

# 进行检索生成
python generate.py
```

构建流程可见[process.md](docx/process.md)

---

### 知识库构建

#### 1. **知识点抽取**
使用`qwen2.5:14b`从医学试题中抽取考题知识点。清洗后数据存储在[knowledge.json](data/knowledge/knowledge.json)中。

#### 2. **关系抽取**
同样使用`qwen2.5:14b`从抽取的知识点中识别实体与关系。数据存储在[graph.json](data/knowledge/graph.json)中。模型抽取时需指定实体与关系类别，避免错误抽取。

#### 3. **Neo4j构建**
使用[Neo4jBuilder.py](process/data/Neo4jBuilder.py)将知识图谱数据导入Neo4j图数据库，以支持高效检索。

---

### RAG流程

#### 1. **嵌入模型**
使用`bge-large-zh-v1.5`进行实体和知识点编码

#### 2. **Neo4j数据提取**
使用[Neo4jEntityFetcher.py](process/rag/Neo4jEntityFetcher.py)从Neo4j提取实体，提供基于属性、标签等条件的查询接口。

#### 3. **FAISS索引生成**
通过[IndexBuild.py](process/rag/IndexBuild.py)构建FAISS索引，用于快速匹配实体和知识点。

#### 4. **RAG工作流**
在[ragWorkflow.py](process/rag/ragWorkflow.py)中，输入关键词，利用FAISS索引进行实体匹配，提取相关知识点，生成医学试题。


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

在上述数据准备的基础上，我们使用`metagpt`构建试题，启动脚本为[main.py](main.py),相关agent配置位于[agent](agent),其他脚本位于[utils](utils)









