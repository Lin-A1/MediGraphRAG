import json
import random
import re
import os

from langchain.llms import Ollama
from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.config2 import Config
from .knowCleaner import knowClean


def parse_json(rsp):
    pattern = r"```json(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    json = match.group(1) if match else rsp
    return json


def write_json_to_file(data, file_path):
    """将JSON格式的数据作为数组元素追加到文件"""
    try:
        # 先读取现有内容，如果文件为空则创建空数组
        try:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    content = json.load(f)  # 尝试读取现有的JSON数据
                    if not isinstance(content, list):
                        raise ValueError("文件内容不是一个合法的JSON数组")
                except json.JSONDecodeError:
                    content = []  # 如果文件为空或格式不正确，创建一个空数组
        except FileNotFoundError:
            content = []

        # 添加新的数据
        content.append(data)

        # 将更新后的数组写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=4)

    except Exception as e:
        logger.info(f"写入出错")


class questionGeneration(Action):
    def __init__(self, config=None, context=None):
        if config is None:
            # 获取当前文件的绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建上级目录中 config 文件夹下的 deepseek-r1.yaml 的绝对路径
            config_path = os.path.join(current_dir, "../config/deepseek-r1.yaml")
            # 将路径标准化为绝对路径
            config_path = os.path.abspath(config_path)
            # 使用绝对路径加载配置
            config = Config.from_home(config_path)

        # 调用父类构造函数
        super().__init__(config=config, context=context)

    PROMPT_TEMPLATE: str = """
        你是医学领域的专业大学教授，现在需要你根据我传递给你的知识库内容构建一道选择题，以考察考生的专业能力

        **输出要求:**

        - 我发给你的内容是相关需要生成的试题的知识点
        - 你需要确保你给的题目具有逻辑性且有唯一正确答案
        - 基于知识库内容或部分内容进行试题的生成
        - 试题考察尽量不要过于简单，需要有一定难度，题目不应该过于简单，比如能在题干中直接看出答案。
        - 你需要返回题目、选项、答案、解析，其中选项必须为ABCD四个选项
        - 确保输出是紧凑格式的有效JSON格式，不包含任何其他解释、转义符、换行符或反斜杠
        - 请确保生成的试题的专业性，确保语言的逻辑能力与问题提问方式的合理性以及题目生成的正确性
        - 按照题目题型特点生产试题，特点为：{qtype}

        **知识库内容:**
        {knowledge_description}

        **输出案例（仅提供格式输出和题型格式，不提供知识点参考，可以简单借鉴出题目方式但禁止完全仿照相同格式进行试题生成）：**

        {case}

        """

    name: str = "questionGeneration"

    async def run(self, knowledge_description: str):
        qtype = [
            {
                "名称": "概念判断题",
                "特点": "针对基本概念的理解与记忆，要求考生判断对错或从多个选项中选择符合题干描述的正确答案。",
                "输出案例": [
                    {
                        "topic": "有关人体内控制系统中的调定点，错误的描述是？",
                        "options": {
                            "A": "调定点通过负反馈调节",
                            "B": "调定点是内环境稳定的标准值",
                            "C": "调定点不可调节",
                            "D": "调定点可受环境因素影响"
                        },
                        "answer": "C",
                        "parse": "调定点是一个通过反馈机制调节的标准值，通常不受外部因素直接改变，因此错误的描述是C选项。"
                    },
                    {
                        "topic": "不参与构成核小体核心颗粒的组蛋白是？",
                        "options": {
                            "A": "H1",
                            "B": "H2A",
                            "C": "H2B",
                            "D": "H3"
                        },
                        "answer": "A",
                        "parse": "核小体核心颗粒由H2A、H2B、H3和H4组成，H1不参与其中。"
                    },
                    {
                        "topic": "左下肢骨折固定6周后变细，这种病变属于？",
                        "options": {
                            "A": "骨萎缩",
                            "B": "骨质疏松",
                            "C": "骨变形",
                            "D": "骨折不愈合"
                        },
                        "answer": "A",
                        "parse": "骨折后固定期骨头会因为缺乏负重而出现骨萎缩，导致骨骼变细。"
                    },
                    {
                        "topic": "非寒战产热作用最强的组织是？",
                        "options": {
                            "A": "肝脏",
                            "B": "骨骼肌",
                            "C": "脂肪组织",
                            "D": "大脑"
                        },
                        "answer": "B",
                        "parse": "骨骼肌通过剧烈运动是非寒战产热作用最强的组织。"
                    },
                    {
                        "topic": "蛋白质常发生磷酸化的氨基酸残基有？",
                        "options": {
                            "A": "Ser、Thr、Tyr",
                            "B": "Pro、Glu、His",
                            "C": "Cys、Asn、Met",
                            "D": "Leu、Val、Ala"
                        },
                        "answer": "A",
                        "parse": "磷酸化常发生在Ser、Thr、Tyr等氨基酸残基上。"
                    },
                    {
                        "topic": "急性细菌性炎症早期主要渗出细胞是？",
                        "options": {
                            "A": "中性粒细胞",
                            "B": "单核细胞",
                            "C": "淋巴细胞",
                            "D": "嗜酸性粒细胞"
                        },
                        "answer": "A",
                        "parse": "急性细菌性炎症早期渗出细胞主要是中性粒细胞。"
                    },
                    {
                        "topic": "肾脏分泌NH3和NH4+的描述，正确的有？",
                        "options": {
                            "A": "主要通过近曲小管分泌",
                            "B": "有助于维持酸碱平衡",
                            "C": "与尿液酸性有关",
                            "D": "与肾单位的浓缩功能无关"
                        },
                        "answer": "B, C",
                        "parse": "肾脏通过分泌NH3和NH4+来帮助维持酸碱平衡，并与尿液酸性有关。"
                    }
                ]

            },
            {
                "名称": "机制分析题",
                "特点": "考察生理、生化、病理等机制或过程的理解。",
                "输出案例": [
                    {
                        "topic": "骨骼肌细胞横管膜L型钙通道激活后的生理效应是？",
                        "options": {
                            "A": "肌肉收缩",
                            "B": "肌肉松弛",
                            "C": "钙离子进入细胞",
                            "D": "钠离子外流"
                        },
                        "answer": "A",
                        "parse": "L型钙通道的激活导致钙离子流入肌细胞，触发肌肉收缩。"
                    },
                    {
                        "topic": "在糖无氧酵解代谢调节中，磷酸果糖激酶-1最强别构激活剂是？",
                        "options": {
                            "A": "ATP",
                            "B": "AMP",
                            "C": "NADH",
                            "D": "ADP"
                        },
                        "answer": "B",
                        "parse": "AMP是磷酸果糖激酶-1的强别构激活剂，在糖无氧酵解中起重要作用。"
                    },
                    {
                        "topic": "导致糖尿病酮症的主要脂代谢紊乱是？",
                        "options": {
                            "A": "脂肪酸氧化增加",
                            "B": "胆固醇合成增加",
                            "C": "脂肪酸合成减少",
                            "D": "酮体合成增加"
                        },
                        "answer": "D",
                        "parse": "糖尿病酮症的发生与酮体合成增加密切相关，尤其在胰岛素不足时。"
                    },
                    {
                        "topic": "关于NO对循环系统作用的描述，正确的有？",
                        "options": {
                            "A": "NO通过血管扩张降低血压",
                            "B": "NO促进血小板聚集",
                            "C": "NO增加心脏输出量",
                            "D": "NO与抗炎作用有关"
                        },
                        "answer": "A, D",
                        "parse": "NO通过血管扩张降低血压，并具有抗炎作用。"
                    },
                    {
                        "topic": "慢性阻塞性肺疾病患者发生肺动脉高压的最重要机制是？",
                        "options": {
                            "A": "肺小动脉的重塑",
                            "B": "血液黏稠度增加",
                            "C": "氧气分压下降",
                            "D": "肺泡通气量增加"
                        },
                        "answer": "A",
                        "parse": "慢性阻塞性肺疾病导致的肺小动脉重塑是引发肺动脉高压的最重要机制。"
                    },
                    {
                        "topic": "转运肝合成的内源性胆固醇至全身组织的脂蛋白是？",
                        "options": {
                            "A": "低密度脂蛋白（LDL）",
                            "B": "高密度脂蛋白（HDL）",
                            "C": "极低密度脂蛋白（VLDL）",
                            "D": "胆固醇酯"
                        },
                        "answer": "A",
                        "parse": "低密度脂蛋白（LDL）负责转运肝脏合成的胆固醇至全身组织。"
                    },
                    {
                        "topic": "参加嘌呤核苷酸从头合成途径的主要关键酶是？",
                        "options": {
                            "A": "磷酸果糖激酶-1",
                            "B": "酰基转移酶",
                            "C": "PRPP合成酶",
                            "D": "腺苷酸激酶"
                        },
                        "answer": "C",
                        "parse": "PRPP合成酶是嘌呤核苷酸从头合成途径的关键酶。"
                    }
                ]

            },
            {
                "名称": "症状诊断题",
                "特点": "通过患者的症状、体征和实验室检查结果，采用通俗化的语言，模拟病例或描绘场景，确保描述能引导考生通过归纳和提取信息来作答，考察考生的临床推理能力。注意一般只进行病状的描述，而不是直接说明其的疾病，强调一下疾病和症状是不一样的，概念多数时候不能混用，如‘肌无力一般不会直接描述，多数时候表述是眼睑下垂四肢乏力’",
                "输出案例": [
                    {
                        "topic": "23岁男性，发热、寒战，伴乏力和脾肿大，最可能的诊断是？",
                        "options": {
                            "A": "传染性单核细胞增多症",
                            "B": "急性白血病",
                            "C": "淋巴瘤",
                            "D": "慢性肝炎"
                        },
                        "answer": "A",
                        "parse": "发热、寒战伴乏力和脾肿大常见于传染性单核细胞增多症。"
                    },
                    {
                        "topic": "45岁男性，右季肋部胀痛，既往乙肝10余年，最可能的诊断是？",
                        "options": {
                            "A": "肝硬化",
                            "B": "胆囊炎",
                            "C": "胃溃疡",
                            "D": "肝癌"
                        },
                        "answer": "A",
                        "parse": "右季肋部胀痛伴有长期乙肝史，最可能的诊断是肝硬化。"
                    },
                    {
                        "topic": "18岁女性，乏力、面色苍白，血常规提示小细胞低色素贫血，最可能的诊断是？",
                        "options": {
                            "A": "缺铁性贫血",
                            "B": "地中海贫血",
                            "C": "巨幼细胞贫血",
                            "D": "慢性病贫血"
                        },
                        "answer": "A",
                        "parse": "小细胞低色素贫血和乏力、面色苍白常见于缺铁性贫血。"
                    }
                ]

            },
            {
                "名称": "治疗与处理题",
                "特点": "关注疾病的治疗原则、首选药物或手术方式。",
                "输出案例": [
                    {
                        "topic": "急性前壁心肌梗死，急诊处理最正确的是？",
                        "options": {
                            "A": "立刻进行冠脉造影",
                            "B": "使用溶栓药物",
                            "C": "进行紧急手术",
                            "D": "静脉输液和止痛"
                        },
                        "answer": "B",
                        "parse": "急性前壁心肌梗死的急诊处理应尽早使用溶栓药物。"
                    },
                    {
                        "topic": "15岁男性肾病综合征患者，最主要的治疗药物是？",
                        "options": {
                            "A": "激素类药物",
                            "B": "抗生素",
                            "C": "免疫抑制剂",
                            "D": "利尿剂"
                        },
                        "answer": "A",
                        "parse": "肾病综合征的主要治疗药物是激素类药物，用于减轻肾脏炎症反应。"
                    }
                ]

            },
            {
                "名称": "综合型分析题",
                "特点": "涉及多学科内容，综合考察考生的知识应用能力。",
                "输出案例": [
                    {
                        "topic": "可通过激活酪氨酸激酶受体完成细胞信号转导的配体有？",
                        "options": {
                            "A": "胰岛素",
                            "B": "生长因子",
                            "C": "细胞因子",
                            "D": "激素"
                        },
                        "answer": "A, B",
                        "parse": "胰岛素和生长因子都可以通过激活酪氨酸激酶受体来完成细胞信号转导。"
                    },
                    {
                        "topic": "6年前心肌梗死，评估目前心功能的检查方法包括？",
                        "options": {
                            "A": "心电图",
                            "B": "超声心动图",
                            "C": "胸片检查",
                            "D": "心肌酶检测"
                        },
                        "answer": "B",
                        "parse": "超声心动图是评估心功能最常用的检查方法，能够全面反映心脏的收缩与舒张功能。"
                    }
                ]

            },
            {
                "名称": "题干分析题",
                "特点": "给定一个医学场景或背景，要求考生基于题干内容提出**多个问题**，考察其推理、分析与综合能力。同时通过在题干描述中加入与诊断不完全相关的症状和检查结果，考察考生从混杂信息中筛选关键信息、排除干扰项并作出正确诊断的能力。注意一般只进行病状的描述，而不是直接说明其的病名，如‘肌无力一般不会直接描述，多数时候表述是眼睑下垂四肢乏力’",
                "输出案例": [
                    {
                        "topic": "一名65岁男性患者，长期吸烟，近半年有持续咳嗽、咳痰，偶有气短，体检时发觉右侧胸部有哑音，胸片显示右肺上叶局部阴影。以下是该患者可能的诊断问题：",
                        "questions": [
                            {
                                "question": "该患者的最可能诊断是？",
                                "options": {
                                    "A": "肺炎",
                                    "B": "肺结核",
                                    "C": "慢性阻塞性肺疾病（COPD）",
                                    "D": "肺癌"
                                },
                                "answer": "D",
                                "parse": "患者的吸烟史、持续咳嗽、咳痰和胸片阴影提示可能存在肺癌，尤其是右肺上叶局部阴影。"
                            },
                            {
                                "question": "对于这种患者，应该做的首项检查是什么？",
                                "options": {
                                    "A": "肺功能测试",
                                    "B": "CT扫描",
                                    "C": "血气分析",
                                    "D": "支气管镜检查"
                                },
                                "answer": "B",
                                "parse": "CT扫描是评估肺部阴影、肿瘤及肺部病变的金标准检查，能够更清晰地显示肿瘤的大小、位置和特征。"
                            },
                            {
                                "question": "该患者是否需要进行手术治疗？",
                                "options": {
                                    "A": "不需要，目前可以药物治疗",
                                    "B": "需要，根据肿瘤大小和病变位置决定",
                                    "C": "需要，所有肺癌患者均需要手术",
                                    "D": "不需要，应该采取放疗治疗"
                                },
                                "answer": "B",
                                "parse": "是否需要手术治疗要根据肿瘤的大小、位置及转移情况来决定。早期肺癌可能需要手术治疗，而晚期则可能需要化疗或放疗。"
                            }
                        ]
                    },
                    {
                        "topic": "一名45岁女性患者，突然出现剧烈腹痛，伴有恶心、呕吐，体检发现腹部触痛明显，血常规检查显示白细胞增高。以下是该患者的分析问题：",
                        "questions": [
                            {
                                "question": "该患者最可能的诊断是？",
                                "options": {
                                    "A": "急性胃炎",
                                    "B": "急性阑尾炎",
                                    "C": "急性胰腺炎",
                                    "D": "消化性溃疡穿孔"
                                },
                                "answer": "C",
                                "parse": "剧烈腹痛、恶心呕吐和白细胞增高提示急性胰腺炎，尤其是在女性患者中更为常见。"
                            },
                            {
                                "question": "下一步最重要的检查是什么？",
                                "options": {
                                    "A": "腹部X线检查",
                                    "B": "腹部CT扫描",
                                    "C": "腹部超声",
                                    "D": "血清胰酶检查"
                                },
                                "answer": "B",
                                "parse": "CT扫描能够清晰显示胰腺的病变范围，有助于确认胰腺炎的诊断及排除其他可能的腹部病变。"
                            },
                            {
                                "question": "该患者的急性胰腺炎治疗中最重要的措施是什么？",
                                "options": {
                                    "A": "抗生素治疗",
                                    "B": "静脉补液",
                                    "C": "止痛药治疗",
                                    "D": "手术治疗"
                                },
                                "answer": "B",
                                "parse": "急性胰腺炎的治疗关键是静脉补液，保持水、电解质平衡，避免进一步加重病情。"
                            }
                        ]
                    },
                    {
                        "topic": "一名60岁男性患者，长期高血压，出现头痛、视力模糊、呕吐，神经系统检查显示轻度瘫痪。CT扫描显示大脑内有出血影像。以下是该患者可能的诊断问题：",
                        "questions": [
                            {
                                "question": "该患者最可能的诊断是？",
                                "options": {
                                    "A": "急性脑梗死",
                                    "B": "脑出血",
                                    "C": "高血压危象",
                                    "D": "颅内肿瘤"
                                },
                                "answer": "B",
                                "parse": "患者的高血压病史及CT扫描的出血影像提示脑出血。头痛、视力模糊及神经系统症状也符合脑出血的表现。"
                            },
                            {
                                "question": "治疗该患者的首要措施是什么？",
                                "options": {
                                    "A": "降压治疗",
                                    "B": "手术治疗",
                                    "C": "止血药物",
                                    "D": "抗凝治疗"
                                },
                                "answer": "A",
                                "parse": "对脑出血患者而言，首先要控制血压，避免进一步加重出血。降压治疗应谨慎进行，避免血压过低。"
                            },
                            {
                                "question": "若该患者的出血量较大，可能需要采取什么措施？",
                                "options": {
                                    "A": "紧急手术",
                                    "B": "抗血小板治疗",
                                    "C": "使用血管收缩药",
                                    "D": "静脉补液"
                                },
                                "answer": "A",
                                "parse": "大出血可能需要紧急手术治疗，进行血肿清除和止血，以防止生命危险。"
                            }
                        ]
                    },
                    {
                        "topic": "一名30岁女性患者，出现双侧膝关节疼痛，伴有晨僵，持续时间较长。她有家族性类风湿性关节炎病史。以下是该患者可能的诊断问题：",
                        "questions": [
                            {
                                "question": "该患者最可能的诊断是？",
                                "options": {
                                    "A": "骨关节炎",
                                    "B": "类风湿性关节炎",
                                    "C": "痛风",
                                    "D": "强直性脊柱炎"
                                },
                                "answer": "B",
                                "parse": "患者的膝关节疼痛、晨僵以及家族史符合类风湿性关节炎的表现，尤其是双侧关节受累。"
                            },
                            {
                                "question": "为确诊类风湿性关节炎，应该做什么检查？",
                                "options": {
                                    "A": "X光检查",
                                    "B": "血清抗环瓜氨酸肽抗体（CCP）检查",
                                    "C": "关节超声",
                                    "D": "尿酸水平检查"
                                },
                                "answer": "B",
                                "parse": "血清抗环瓜氨酸肽抗体（CCP）检查是类风湿性关节炎的特异性检查，能够帮助确诊。"
                            },
                            {
                                "question": "如果确诊为类风湿性关节炎，最重要的治疗措施是什么？",
                                "options": {
                                    "A": "非甾体抗炎药（NSAIDs）",
                                    "B": "糖皮质激素治疗",
                                    "C": "抗风湿药物（DMARDs）",
                                    "D": "手术治疗"
                                },
                                "answer": "C",
                                "parse": "抗风湿药物（DMARDs）是类风湿性关节炎的基础治疗药物，能够减缓疾病进展，控制症状。"
                            }
                        ]
                    }
                ]
            }

        ]
        # knowledge_description = parse_json(knowledge_description)
        # q = random.choice(qtype)
        # qtype = q['名称'] + ':' + q['特点']
        # case = random.choice(q['输出案例'])
        # prompt = self.PROMPT_TEMPLATE.format(knowledge_description=knowledge_description[-1], qtype=qtype, case=case)
        # rsp = await self._aask(prompt)
        # text = parse_json(rsp)
        # try:
        #     text_dict = json.loads(text)
        #     write_json_to_file(text_dict, "save/questionGeneration.json")
        # except json.JSONDecodeError:
        #     logger.info(f"输出格式错误")
        # return text

        # 初始化 Ollama 模型
        # llm = Ollama(model="qwen2.5:14b")
        llm = Ollama(model="glm4:latest")

        # 定义用于模型判断的 Prompt
        judge_prompt = """
        你是一个医学考试题目生成专家。请判断以下题目是否符合以下规则：
        1. 题目不应该过于简单，比如能在题干中直接看出答案。
        2. 题目需要大致符合题型特点。
        3. 题目质量需要有一定保障
    
        若非题目符合规则，请返回True，若出现较大明显问题，返回False,尽量放宽规则，若题干中直接出现答案的题目必须返回False

        题目：{full_question}
        
        返回示例：
        ```True/False```
        """

        def check_generated_result(full_question):
            prompt = judge_prompt.format(
                full_question=full_question
            )
            response = llm(prompt)
            if "True" in response:
                return True
            else:
                logger.info(f'\n{response}\n')
                return False

        # 生成的题目
        q = random.choice(qtype)
        qtype = '试题类型' + '-' + q['名称'] + '-特点：' + q['特点']
        case = f"""
        ```json
        {random.choice(q['输出案例'])}
        ```
        """
        prompt = self.PROMPT_TEMPLATE.format(knowledge_description=knowledge_description[-1], qtype=qtype, case=case)
        rsp = await self._aask(prompt)
        text = parse_json(rsp)

        try:
            text_dict = json.loads(text)
            # 将整个问题作为一个整体
            full_question = qtype+'\n'+str(json.loads(text))

            # 判断是否符合要求
            is_valid = check_generated_result(full_question)

            if is_valid:
                write_json_to_file(text_dict, "save/questionGeneration.json")
                logger.info(f"生成的题目符合要求，已保存")
            else:
                logger.info(f"生成的题目不符合要求，未保存")
        except json.JSONDecodeError:
            logger.info(f"输出格式错误")
        # return
        return rsp


class questionGenerator(Role):
    name: str = "Question generator"
    profile: str = "进行试题的生成"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([questionGeneration])
        self._watch([knowClean])
        # self._watch([UserRequirement])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: 准备执行 {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        context = self.get_memories()
        knowledge_description = await todo.run(context)
        msg = Message(knowledge_description=knowledge_description, role=self.profile, cause_by=type(todo))

        return msg
