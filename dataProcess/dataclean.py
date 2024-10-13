from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

import os
from docx import Document
import json
from tqdm import tqdm

import warnings

warnings.filterwarnings("ignore")


def read_docx(file_path):
    doc = Document(file_path)
    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)
    return '\n'.join(text)


folder_path = '/home/lin/work/code/DeepLearning/LLM/file/医疗语料/西医综合/'
all_content = []

# 获取所有 .docx 文件的列表
docx_files = [filename for filename in os.listdir(folder_path) if filename.endswith('.docx')]

# 使用 tqdm 添加进度条
for filename in tqdm(docx_files, desc='Processing files'):
    file_path = os.path.join(folder_path, filename)
    content = read_docx(file_path)
    content = content.split('\n\n')
    all_content.extend(content)

content = all_content

systemContent = r"""你是我的医学文件整理助理，我有题目要你帮我整理

要求如下：
- 我发给你的题目包含题目、答案、解析
- 你需要返回一个这一个题目的详细知识点
- 我发给你的不一定的可以会出错，会发给你空字符串或者非试题，有或者试题没有答案或解析，这个时候你返回空给我即可
- 你不需要返回题目相关信息给我，比如选项
- 只需要返回指定内容，不需要其他内容
- 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠

输出案例：
{{'knowledge':'肺结节是指在胸部影像学检查（如CT或X光）中发现的小于3厘米的局部肿块，可以是良性（如肉芽肿或感染后的瘢痕）或恶性（如肺癌）。诊断时，需要综合考虑结节的影像学特征，如边缘是否光滑、是否有钙化以及形状和密度等。此外，医生通常会根据患者的吸烟史、年龄、家族史等风险因素来判断结节的性质。随访观察非常重要，定期复查CT影像可以帮助监测结节是否增长，从而指导后续的治疗方案。对于疑似恶性的结节，可能需要进行病理学检查，如穿刺活检，以获得确诊。'}}

"""

prompt_template = ChatPromptTemplate.from_messages(
    [("system", systemContent), ("user", "{text}")]
)

model = Ollama(model="qwen2.5")
parser = JsonOutputParser()
chain = prompt_template | model | parser

if not os.path.exists('../data/knowledge.json'):
    with open('../data/knowledge.json', 'w') as f:
        json.dump([], f)

# 读取现有数据
with open('../data/knowledge.json', 'r') as f:
    responses = json.load(f)

for i in tqdm(content):
    time = 0
    while True:
        try:
            response = chain.invoke({"text": i})
            if isinstance(response, dict):
                if response:
                    responses.append(response)  # 添加响应
                    # 立即写入文件
                    with open('../data/knowledge.json', 'w') as f:
                        json.dump(responses, f, ensure_ascii=False, indent=4)
                    break
                else:
                    break
        except:
            time += 1
            if time > 5:
                break
            pass
