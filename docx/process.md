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

## 知识库构建

- **[dataProcess.ipynb](../process/data/dataProcess.ipynb)**
![rag](https://github.com/Lin-A1/MediGraphRAG/blob/main/docx/images/create.png?raw=true)
### 知识图谱构建

#### 1. 知识点抽取

- **[KnowledgeExtractor.py](../process/data/KnowledgeExtractor.py)**

通过`qwen2.5:14b`从医学试题中抽取考题知识点，我们需要设置`promat`暗示模型需要进行知识的提取，而不是进行该题目的解题

`folder_path`的地址需要换成你的医疗试题数据集的地址，同时注意你的文档的清洗方式需要修改

从每一道试题中提取一个知识点，将其转换为`dict`格式，以便后续转为`json`,值得注意的是由于模型处理速度偏慢，且由于本地数据清洗可能存在内存溢出，模型宕机等情况，在这里我选择进行多次`IO操作`，牺牲时间以保证安全性的策略，在每次读取后立即进行数据的存储

清洗后的数据存储在[knowledge.json](../data/knowledge/knowledge.json)中

<details>
<summary> knowledge.json </summary>
    
 ```json
 [
    {
        "knowledge": "急性造血停滞的特点包括突然出现的全血细胞减少、网织红细胞可降至零以及骨髓中可见巨大原红细胞。此病通常在无血液病的患者中发生，且其病程常呈自限性，在适当的支持治疗下可以自然恢复。因此选项A（均发生于无血液病的患者）不符合急性造血停滞的特点。"
    },
    {
        "knowledge": "老年人行走时不慎滑倒后出现右髋部疼痛、局部压痛及下肢短缩和外旋畸形，提示可能发生髋部损伤。根据症状描述，最可能的诊断是股骨转子间骨折。此部位骨折的特点包括短缩外旋畸形，且患者的年龄和跌倒方式增加了此类骨折的可能性。其他选项如髋关节脱位、髋臼骨折等虽然也可能导致类似的局部表现，但结合患者的具体体征，B项更符合临床实际情况。"
    },
    {
        "knowledge": "梗阻性黄疸的B超诊断最直接证据是肝内胆管普遍扩张以及胆总管直径增大。选项A中的描述‘肝内胆管普遍扩张，胆总管直径1.5cm’符合这一特征。因此，A是最直接的支持梗阻性黄疸诊断的结果。"
    }
  ]
  
 ```
</details>
   
#### 2. 关系抽取

- **[GraphBuilder.py](../process/data/GraphBuilder.py)**

在前面我们提取知识点的基础上从知识点中提取数据，同样的我们采用`qwen2.5:14b`进行演本的提取，大致流程与前面知识点抽取的一致，但是需要注意的是为我们需要在`promat`中暗示好我们所需要的实体，与关系类别，否则他将可能抽取各种奇怪的实体与关系，这会让我们在后期进行知识融合的过程十分不利

<details>
<summary> 实体关系 </summary>

```
- 实体字段
疾病（Disease）：疾病名称、疾病编码（如ICD-10）、描述、分类（如慢性病、传染病等）。
药物（Drug）：药物名称、剂量、适应症、禁忌、常见副作用。
症状（Symptom）：症状名称、描述、严重程度、出现频率。
治疗方法（Treatment）：治疗方案、方法（如手术、药物治疗）、疗效、适应症。
检查项目（Test）：检查名称、目的、结果范围、相关疾病。

- 关系字段
疾病与症状：哪些症状与哪些疾病相关联（例如，咳嗽与肺炎）。
疾病与药物：哪些药物用于治疗特定疾病（例如，阿莫西林用于治疗细菌感染）。
症状与检查项目：某些症状需要进行哪些检查（例如，咳嗽需要进行胸部X光）。
药物与副作用：药物可能引起的副作用（例如，阿司匹林可能导致胃肠不适）。

关系应当包括但不限于以下：["导致症状", "伴随症状", "治疗方法", "疗效", "风险因素", "保护因素", "检查方法", "检查指标", "高发人群", "易感人群", "药物治疗", "药物副作用", "病理表现", "生物标志物", "发生率", "预后因素", "病因", "传播途径", "预防措施", "生活方式影响", "相关疾病", "诊断标准", "自然病程", "临床表现", "并发症", "危险信号", "遗传因素", "环境因素", "生活方式干预", "治疗费用", "治疗反应", "康复措施", "心理影响", "社会影响"]

```

</details>

由于我们任务处理的字段过多，我们实行两步走的策略构建工作流，将知识中的实体抽取后，再让模型从中寻觅关系
 
初步的知识图谱数据存储在[graph.json](data/knowledge/graph.json)中

<details>
<summary> 图谱存储格式 </summary>
    
```json
{
  "knowledge": "胰岛素是调节血糖水平的重要激素，胰腺是其主要分泌腺体。",
  "entities": [
    {
      "entity": "胰岛素",
      "type": "激素",
      "description": "调节血糖水平的激素"
    },
    {
      "entity": "血糖水平",
      "type": "生理指标",
      "description": "血液中的葡萄糖含量"
    },
    {
      "entity": "胰腺",
      "type": "器官",
      "description": "分泌胰岛素的腺体"
    }
  ],
  "relation": [
    {
      "entity1": "胰岛素",
      "relation": "调节",
      "entity2": "血糖水平"
    },
    {
      "entity1": "胰岛素",
      "relation": "主要分泌腺体",
      "entity2": "胰腺"
    }
  ]
}

```
    
</details>
    
    
比较遗憾的是由于大模型幻觉的原因，大模型出现了私自篡改我们字段的情况，比如最终生成的数据中没有`knowledge`,实体间他们使用了别的变量名等，目前这种情况可以通过[GraphNormalizer.py](../process/data/GraphNormalizer.py)中的`validate_json_format`函数进行错误的定位，`revise_format`函数配合大模型进行修复，但是具体出错的修改方式，可能得根据不同的基座模型修改

大模型有比较致命的弱点是他在知识图谱抽取这方面，运行效率并不高，这一步可以通过传统NLP进行关系的抽取

#### 3. Neo4j构建

- **[Neo4jBuilder.py](../process/data/Neo4jBuilder.py)**
  
前面处理的存储格式明显不足以我们进行图片的检索，故我们选择使用Neo4j进行我们图谱的存取。

Neo4j作为一个图数据库，具有更好的图谱检索能力以及更严格的格式要求

![graph](https://github.com/Lin-A1/MediGraphRAG/blob/main/docx/images/graph.png?raw=true)

我们以`relation`、`entity`、`description`、`type`为实体(由于不同知识点下同一个实体的描述的方面不一致，故我们构建多个描述实体以获取更为全面的描述),构建实体知识指向和实体属性关系，以便后续进行知识检索

### RAG

- **[ragProcess.ipynb](../process/rag/ragProcess.ipynb)**
![rag](https://github.com/Lin-A1/MediGraphRAG/blob/main/docx/images/rag.png?raw=true)


#### 1. 嵌入模型

- **[Embedding.py](../process/rag/Embedding.py)**

调用`bge-large-zh-v1.5`- `https://huggingface.co/BAAI/bge-large-zh-v1.5 `后续可能考虑更换医疗领域的预训练嵌入模型

#### 2. Neo4j数据提取

- **[Neo4jEntityFetcher.py](../process/rag/Neo4jEntityFetcher.py)**

我们根据后续建模需求，分别构建了根据属性、标签、ID获取实体的方法以及获取全部实体的方法

#### 3. FAISS索引生成

- **[IndexBuild.py](../process/rag/IndexBuild.py)**

我们这里使用前面定义的`Embedding`模型进行`知识点`、`实体`的编码，仅存储编码后的数据以及使用numpy存储相对应的neo4j的id，我们这里的是`欧几里得距离`进行相似度计算

#### 4. 搭建RAG工作流生成实体

- **[ragWorkflow.py](../process/rag/ragWorkflow.py)**

到这一步我们开始调用前面三点的数据进行搭建我们的`医学试题生成`任务的`大模型工作流`

我们输入关键词，如`糖尿病`，读取`faiss`的索引文件，使用`faiss`的相似度计算接口进行文本的匹配，其中匹配的可能存在`实体`、`知识点`，我们采取的处理策略是：

1. `知识点`：提取知识点相关实体以及这些实体的类型与描述
2. `实体`：提取该实体的类型与描述，以及有关系的实体、相关知识点

这些数据整理出来后仍欠缺解释能力，如实体之间的关系我们直接传递给大模型，再赋予其他任务会导致模型的解释能力下降，以及未整理的数据过长导致模型的任务能力下降，我们构建一个双模型的工作流来进行数据的解释与实体的生成

<details>
<summary> 解释模型prompt </summary>
    
 ```
    你是医学领域的专业大学教授，现在需要你根据我给你的数据描述出这段数据表达的知识点

    **输出要求:**
    
    - 我发给你的内容中包括我需要描述的知识点、以及与他有关的实体与实体的解释
    - 我给你的内容中的描述、类型、相关知识点、以及与他有关的实体可能有多种，你需要完整的描述
    - 你仅需要描述相关内容，不需要额外拓展
    - 尽量以严谨的科学口吻描述完整的描述
    - 返回内容为一段话即可，不需要复杂的格式
  
 ```
</details>

我们匹配相关的k个实体/知识点，进入我们的解释模型，生成k个考点，最后prompt进行任务的输出，实现通过一个关键词生成多考点的`基于医学知识图谱的RAG大模型工作流`


<details>
<summary> 任务模型prompt </summary>
    
```
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

```
</details>



<details>
<summary> 模型输出 </summary>
    
```
{'topic': '对于糖尿病患者而言，在治疗过程中若出现酮症酸中毒，应首选以下哪种治疗方法', 'options': {'A': '口服降糖药', 'B': '静脉输注葡萄糖加胰岛素', 'C': '口服补液盐', 'D': '使用胰岛素泵'}, 'answer': 'B', 'parse': '酮症酸中毒是糖尿病急性并发症之一，需要紧急处理。通过静脉输注葡萄糖和胰岛素可以迅速降低血糖水平并纠正酸中毒状态，因此是最优选择。口服降糖药或补液盐在当前情况下可能无法有效控制病情，而使用胰岛素泵虽然有效但并非首选方案。'}

{'topic': '患者出现阵发性高血压、血尿和糖尿等症状，最可能的原因是', 'options': {'A': '糖尿病', 'B': '膀胱嗜铬细胞瘤', 'C': '肾结石', 'D': '高血压病'}, 'answer': 'B', 'parse': '根据描述的症状（阵发性高血压、血尿和糖尿），这些症状与肿瘤导致的激素分泌增加有关，因此最可能的原因是膀胱嗜铬细胞瘤。糖尿病通常表现为持续性的高血糖和多饮多尿等症状，而肾结石主要引起剧烈腰痛或侧腹疼痛，高血压病则不常伴有血尿和糖尿的症状。'}

{'topic': '糖尿病肾病的主要治疗方法不包括以下哪一项', 'options': {'A': '控制血压', 'B': '低蛋白饮食', 'C': '使用糖皮质激素', 'D': '控制血糖'}, 'answer': 'C', 'parse': '在糖尿病肾病的治疗中，不推荐使用糖皮质激素。正确的治疗方法包括控制血压、低蛋白饮食和控制血糖等措施以减缓肾脏损害进程。'}
```
</details>




目前我们选用的基模型为`qwen2.5`,后续我们可以考虑更换将任务模型的基模型更换为医学大模型

### Agent
使用框架metagpt构建。

## 后续任务

1. 处理开源的医学电子字书，扩大数据集
2. 开发增加数据的接口
3. 进行已有代码的封装，优化代码风格，对常用方法进行整合
4. 调用整理的接口，进行任务的快速调用
5. 将嵌入模型与任务模型更换为医学领域大模型















