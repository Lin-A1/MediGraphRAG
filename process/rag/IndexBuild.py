from langchain.vectorstores import FAISS
from langchain.docstore.document import Document
from Neo4jEntityFetcher import Neo4jEntityFetcher
from Embedding import *
from tqdm import tqdm
from langchain.vectorstores import FAISS
import faiss
import numpy as np


uri = "bolt://localhost:7687"  # Neo4j 数据库地址
user = "neo4j"  # Neo4j 用户名
password = "password"  # Neo4j 密码
fetcher = Neo4jEntityFetcher(uri, user, password)
knowledge_entities = fetcher.get_entities_by_label("knowledge")
knowledge_entities.extend(fetcher.get_entities_by_label("entity"))

texts = [i['properties']['name'] for i in knowledge_entities] 
ids = [i['id'] for i in knowledge_entities]

texts = [i['properties']['name'] for i in knowledge_entities] 
ids = [i['id'] for i in knowledge_entities]

model, tokenizer = LoadModel()
def batch_encode_texts(model, tokenizer, texts, batch_size=32):
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size)):
        batch_texts = texts[i:i + batch_size]
        batch_embeddings = encode_text(model, tokenizer, batch_texts)
        embeddings.extend(batch_embeddings)
    return embeddings

embeddings = batch_encode_texts(model, tokenizer, texts, batch_size=64)
embeddings = np.array(embeddings,dtype=np.float32)

dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)  
index.add(embeddings)

faiss.write_index(index, '../../data/faiss_index/faiss_index.index')

np.save('../../data/faiss_index/matedata.npy', ids)