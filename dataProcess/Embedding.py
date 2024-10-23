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
    if os.path.exists(model_path) and os.path.getsize(model_path) > 1e9:
        model = AutoModel.from_pretrained(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)

    else:
        word_vectors = KeyedVectors.load_word2vec_format('../data/vector.txt', binary=False)
        existing_vectors = {word: word_vectors[word] for word in word_vectors.index_to_key}

        model_name = "../model/bge-large-zh-v1.5"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)

        existing_vectors = {word: word_vectors[word] for word in word_vectors.index_to_key}

        vocab_size = len(tokenizer)
        embedding_dim = 1024
        new_embedding = nn.Embedding(vocab_size, embedding_dim)

        for word, index in tokenizer.get_vocab().items():
            if word in existing_vectors:
                new_embedding.weight.data[index] = torch.cat((torch.tensor(existing_vectors[word]), torch.zeros(512)))

        model.embeddings.word_embeddings = new_embedding

        # 保存模型和分词器
        output_dir = "../model/modified_bge-large-zh-v1.5"
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)
        
    return model,tokenizer

def encode_text(model, tokenizer, text, max_length=512):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=max_length)

    model.eval()

    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)

    return embeddings

if __name__ == "__main__":
    # 使用示例
    text = "输入文本"
    model, tokenizer = LoadModel()
    embeddings = encode_text(model, tokenizer, text)
    print(embeddings)