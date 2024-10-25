import warnings
warnings.filterwarnings("ignore")

import os
import pandas as pd
from tqdm import tqdm
from gensim.models import KeyedVectors
from transformers import AutoModel, AutoTokenizer
import torch
import torch.nn as nn

def LoadModel(model_path='../model/modified_bge-large-zh-v1.5'):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  

    # 加载已保存的模型
    if os.path.exists(model_path) and os.path.getsize(model_path) > 1e9:
        model = AutoModel.from_pretrained(model_path).to(device)  
        tokenizer = AutoTokenizer.from_pretrained(model_path)
    else:
        # 加载词向量并处理不存在的词汇
        word_vectors = KeyedVectors.load_word2vec_format('../data/vector.txt', binary=False)
        existing_vectors = {word: word_vectors[word] for word in word_vectors.index_to_key}

        model_name = "../model/bge-large-zh-v1.5"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name).to(device)  
        vocab_size = len(tokenizer)
        embedding_dim = 1024
        new_embedding = nn.Embedding(vocab_size, embedding_dim).to(device)  

        for word, index in tokenizer.get_vocab().items():
            if word in existing_vectors:
                new_embedding.weight.data[index] = torch.cat(
                    (torch.tensor(existing_vectors[word]).to(device), torch.zeros(512, device=device))
                )

        model.embeddings.word_embeddings = new_embedding

        output_dir = "../model/modified_bge-large-zh-v1.5"
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

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