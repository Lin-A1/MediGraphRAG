import warnings
warnings.filterwarnings("ignore")

import yaml
import os
from transformers import AutoModel, AutoTokenizer
import torch


def LoadModel(model_path='../../model/bge-large-zh-v1.5'):
    with open('config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # 解析环境变量
    base_dir = config['base']['dir']
    model_path = os.path.join(base_dir, config['embedding']['path'])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModel.from_pretrained(model_path).to(device)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    return model, tokenizer


def encode_text(model, tokenizer, text, max_length=512):
    device = model.device
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=max_length).to(device)

    model.eval()

    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1).cpu().tolist()
    return embeddings


if __name__ == "__main__":
    # 使用示例
    text = "输入文本"
    model, tokenizer = LoadModel()
    embeddings = encode_text(model, tokenizer, text)
    print(embeddings)
