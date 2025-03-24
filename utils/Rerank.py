import os
import yaml
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch


class Reranker:
    def __init__(self, config_path='config/config.yaml', use_fp16=True):
        """
        初始化重新排序器。

        :param config_path: 配置文件路径（默认为 'config/config.yaml'）
        :param use_fp16: 是否使用 FP16 精度加速计算（默认 True）
        """
        # 加载配置文件
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)

        # 获取基础目录和模型路径
        base_dir = self.config['base']['dir']
        model_rel_path = self.config['rerank']['path']

        # 拼接并规范化模型路径
        self.model_name = os.path.normpath(os.path.join(base_dir, model_rel_path))

        # 加载分词器和模型
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

        # # 如果支持 FP16，则启用混合精度，作者换卡了没显存了qwq
        # if use_fp16 and torch.cuda.is_available():
        #     self.model = self.model.half().cuda()

        # 设置模型为评估模式
        self.model.eval()

    def rerank(self, query, passages, top_k):
        """
        对候选内容进行重新排序，并返回前 top_k 个最相关的内容。

        :param query: 输入的查询文本（如 'what is panda?'）
        :param passages: 候选内容列表（如 ['passage1', 'passage2', ...]）
        :param top_k: 需要保留的最相关内容数量
        :return: 排序后的 (内容, 分数) 列表，按相关性从高到低排序
        """
        # 构造输入对
        pairs = [[query, passage] for passage in passages]

        # 使用分词器处理输入对
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512
        )

        # 将输入移动到 GPU（如果可用），作者换卡了没显存了qwq
        # if torch.cuda.is_available():
        #     inputs = {key: value.cuda() for key, value in inputs.items()}

        # 模型推理
        with torch.no_grad():
            outputs = self.model(**inputs)

        # 获取相关性分数
        scores = outputs.logits.squeeze().cpu().tolist()

        # 如果只有一个候选内容，确保 scores 是列表
        if not isinstance(scores, list):
            scores = [scores]

        # 将内容和分数组合成元组列表
        scored_passages = list(zip(passages, scores))

        # 按分数降序排序
        sorted_passages = sorted(scored_passages, key=lambda x: x[1], reverse=True)

        # 返回前 top_k 个结果
        return sorted_passages[:top_k]


# 示例使用方法
if __name__ == "__main__":
    # 初始化重新排序器
    reranker = Reranker()

    # 输入查询和候选内容
    query = "what is panda?"
    passages = [
        "hi",
        "The giant panda is a bear species endemic to China.",
        "Pandas are known for their distinctive black and white fur.",
        "Pandas primarily eat bamboo."
    ]
    top_k = 2

    # 进行重新排序并获取前 top_k 个结果
    results = reranker.rerank(query, passages, top_k)
    print(results)