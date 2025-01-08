import time
import fire
from metagpt.logs import logger
from metagpt.team import Team
from agent.knowCleaner import knowCleaner
from agent.questionGenerator import questionGenerator
from utils.generate import MedicalKnowledgeFetcher

keywords = [
    "肺炎链球菌",
    "急性心肌梗死",
    "高血压危象",
    "冠状动脉搭桥手术",
    "过敏性紫癜",
    "慢性阻塞性肺疾病（COPD）",
    "糖尿病酮症酸中毒",
    "胃食管反流病（GERD）",
    "阿尔茨海默病",
    "急性肾衰竭",
    "脑动脉瘤",
    "急性白血病",
    "乳腺癌分期",
    "干燥综合症",
    "狼疮性肾炎",
    "高脂血症",
    "甲亢",
    "慢性肝炎",
    "乙型肝炎病毒（HBV）",
    "肝硬化",
    "肝癌早期诊断",
    "肺结核",
    "膀胱癌",
    "脑卒中后遗症",
    "急性胰腺炎",
    "糖尿病视网膜病变",
    "突发性耳聋",
    "哮喘发作",
    "急性中毒性肝病",
    "脊髓损伤",
    "遗传性肾病",
    "强直性脊柱炎",
    "胰岛素抵抗",
    "白细胞减少症",
    "食物中毒",
    "麻疹",
    "肺部CT影像",
    "X射线检查",
    "心脏超声",
    "胎儿心脏病筛查",
    "耳鼻喉科急症",
    "骨质疏松症",
    "过敏性哮喘",
    "免疫系统失调",
    "抗体检测",
    "癌症免疫治疗",
    "抗生素耐药性",
    "抗肿瘤药物",
    "疼痛管理",
    "肺癌早期筛查",
    "慢性支气管炎",
    "低血糖",
    "抗病毒药物",
    "高尿酸血症",
    "小儿麻痹症",
    "甲状腺结节",
    "胰腺癌",
    "肺部感染",
    "维生素D缺乏",
    "肾结石",
    "骨髓增生异常综合症",
    "肺动脉高压",
    "急性肠胃炎",
    "肠易激综合症",
    "胃癌",
    "乳腺癌基因检测",
    "抗肿瘤免疫疗法",
    "抗炎药物",
    "肾脏移植",
    "胆囊炎",
    "急性阑尾炎",
    "白内障手术",
    "强迫症",
    "吸烟与肺部健康",
    "儿童哮喘",
    "病毒性肝炎",
    "甲状腺功能亢进症",
    "多发性硬化症",
    "系统性红斑狼疮",
    "失眠症",
    "疼痛管理",
    "抗生素滥用",
    "帕金森病",
    "类风湿性关节炎",
    "骨折复位",
    "儿童免疫接种",
    "慢性肾病",
    "脓毒症",
    "超声波诊断",
    "小儿疝气",
    "胃溃疡",
    "肌肉萎缩症",
    "过敏性休克",
    "胰腺炎",
    "老年痴呆",
    "疱疹病毒",
    "腹膜炎",
    "心脏骤停",
    "淋巴癌",
    "自闭症谱系障碍",
    "肺结节",
    "胃癌分期",
    "早产儿护理",
    "肾衰竭",
    "肺功能检查",
    "糖尿病并发症",
    "传染病防控",
    "食管癌",
    "神经退行性疾病",
    "抗菌药物使用",
    "骨髓穿刺",
    "血液透析",
    "肠梗阻",
    "电子健康记录",
    "疫苗接种",
    "流感病毒",
    "儿童肥胖症",
    "遗传性心脏病",
    "乳腺超声",
    "癌症筛查",
    "关节置换手术",
    "急性心力衰竭",
    "过敏性鼻炎",
    "早期干预",
    "癫痫发作",
    "乳腺肿块",
    "宫颈癌筛查",
    "儿童肥胖",
    "骨质疏松性骨折",
    "新型冠状病毒",
    "内镜检查",
    "抗肿瘤化疗",
    "慢性胃炎",
    "类风湿性关节炎",
    "结肠癌",
    "癌症放疗",
    "外科手术",
    "慢性胃食管反流病",
    "骨癌"
]

fetcher = MedicalKnowledgeFetcher()


# 查询每个关键词的相关知识
def fetch_knowledge_for_keywords(keywords):
    all_knowledges = {}
    for keyword in keywords:
        knowledges = fetcher.query_knowledge(keyword)
        all_knowledges[keyword] = keyword + '\n'.join(knowledges)
    return all_knowledges


def calculate_time(func):
    """装饰器：计算异步函数执行时间"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()  # 获取开始时间
        result = await func(*args, **kwargs)  # 等待异步函数执行
        end_time = time.time()  # 获取结束时间
        execution_time = end_time - start_time  # 计算花费的时间
        print(f"异步函数 {func.__name__} 执行时间: {execution_time:.6f} 秒")
        return result
    return wrapper


@calculate_time
async def main(
        investment: float = 1000.0,
        n_round: int = 20,
):
    # 批量获取知识
    all_knowledges = fetch_knowledge_for_keywords(keywords)

    # 依次处理每个关键词的知识
    for keyword, idea in all_knowledges.items():
        logger.info(f"Processing knowledge for keyword: {keyword}")
        logger.info(idea)

        team = Team()
        team.hire(
            [
                knowCleaner(),
                questionGenerator(),
            ]
        )

        team.invest(investment=investment)
        team.run_project(idea)
        await team.run(n_round=n_round)


if __name__ == "__main__":
    msg = fire.Fire(main)
