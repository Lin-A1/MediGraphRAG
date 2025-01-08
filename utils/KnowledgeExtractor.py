import os
import json
from docx import Document
from tqdm import tqdm
from langchain_community.llms import Ollama
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
import warnings

warnings.filterwarnings("ignore")


class MedicalQuestionAssistant:
    def __init__(self, folder_path, output_path, model_name="qwen2.5"):
        self.folder_path = folder_path
        self.output_path = output_path
        self.model = Ollama(model=model_name)
        self.parser = JsonOutputParser()
        self.prompt_template = self.create_prompt_template()
        self.content = self.load_content()
        self.responses = self.load_existing_data()

    def create_prompt_template(self):
        system_content = r"""你是我的医学文件整理助理，我有题目要你帮我整理
        
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
        return ChatPromptTemplate.from_messages(
            [("system", system_content), ("user", "{text}")]
        )
    
    def read_docx(self, file_path):
        doc = Document(file_path)
        text = [paragraph.text for paragraph in doc.paragraphs]
        return '\n'.join(text)

    def load_content(self):
        """
        切割方式需要根据不同的文档进行调整
        """
        all_content = []
        docx_files = [f for f in os.listdir(self.folder_path) if f.endswith('.docx')]
        for filename in tqdm(docx_files, desc='Processing files'):
            file_path = os.path.join(self.folder_path, filename)
            content = self.read_docx(file_path).split('\n\n')
            all_content.extend(content)
        return all_content

    def load_existing_data(self):
        if not os.path.exists(self.output_path):
            with open(self.output_path, 'w') as f:
                json.dump([], f)
        with open(self.output_path, 'r') as f:
            return json.load(f)

    def process_questions(self):
        chain = self.prompt_template | self.model | self.parser
        for i in tqdm(self.content):
            retries = 0
            while True:
                try:
                    response = chain.invoke({"text": i})
                    if isinstance(response, dict) and response:
                        self.responses.append(response)
                        with open(self.output_path, 'w') as f:
                            json.dump(self.responses, f, ensure_ascii=False, indent=4)
                        break
                    else:
                        break
                except:
                    retries += 1
                    if retries > 5:
                        break
                    pass


# 使用示例
folder_path = '/home/lin/work/code/DeepLearning/LLM/file/医疗语料/西医综合/'
output_path = '../../data/knowledge.json'
assistant = MedicalQuestionAssistant(folder_path, output_path)
assistant.process_questions()