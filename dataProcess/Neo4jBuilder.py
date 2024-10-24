import warnings
warnings.filterwarnings("ignore")

import json
from tqdm import tqdm
from neo4j import GraphDatabase

with open('../data/graph/graph.json') as file:
    data = json.load(file)

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.session = self.driver.session()
    
    def close(self):
        self.session.close()
        self.driver.close()
    
    def create_node(self, entity_name, entity_type=None):
            if entity_type:
                query = f"MERGE (n:`{entity_type}` {{name: $name}})"
            else:
                query = "MERGE (n {name: $name})"
            self.session.run(query, name=entity_name)

    def create_relationship(self, entity1_name, relation_type, entity2_name, properties=None):
            if properties:
                props = ', '.join([f"{key}: ${key}" for key in properties.keys()])
                query = f"""
                MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                MERGE (a)-[:`{relation_type}` {{{props}}}]->(b)
                """
            else:
                query = f"""
                MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                MERGE (a)-[:`{relation_type}`]->(b)
                """
            self.session.run(query, entity1_name=entity1_name, entity2_name=entity2_name, **(properties or {}))


if __name__ == "__main__":
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "password"
    
    neo4j_handler = Neo4jHandler(uri, user, password)

    for d in tqdm(data):
        knowledge = f"{d['knowledge']}"
        entities = d['entities']
        relation = d['relation']
        if knowledge != '':
            neo4j_handler.create_node(knowledge, "knowledge")
        for entitiy in entities:
            entity_name = f"{entitiy['entity']}"
            entity_type = f"{entitiy['type']}"
            description = f"{entitiy['description']}"
    
            neo4j_handler.create_node(entity_name=entity_name, entity_type=entity_type)
            neo4j_handler.create_node(description)
            if entity_name and description:
                neo4j_handler.create_relationship(entity1_name=entity_name, relation_type='description', entity2_name=description)
    
            if knowledge != '' and entity_name and knowledge:
                neo4j_handler.create_relationship(entity1_name=entity_name, relation_type='knowledge', entity2_name=knowledge)
    
        for rela in relation:
            if rela['entity1']:
                entity1 = f"{rela['entity1']}"
            if rela['entity2']:
                if isinstance(rela['entity2'], list):
                    entity2 = [f"{item}" for item in rela['entity2']]
                else:
                    entity2 = f"{rela['entity2']}"
    
            neo4j_handler.create_node(entity1)

            if entity1 and entity2 and rela['relation']:
                if isinstance(rela['entity2'], list):
                    for e2 in rela['entity2']:
                        neo4j_handler.create_node(e2)
                        neo4j_handler.create_relationship(entity1_name=entity1, relation_type='relation', entity2_name=f"{e2}", properties={'relation': rela['relation']})
                else:
                    neo4j_handler.create_node(entity2)
                    neo4j_handler.create_relationship(entity1_name=entity1, relation_type='relation', entity2_name=entity2, properties={'relation': rela['relation']})

    Neo4jHandler.close()
    



















                