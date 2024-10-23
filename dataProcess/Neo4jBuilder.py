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

    def close(self):
        self.driver.close()

    def entity_exists(self, entity_name, entity_type=None):
        with self.driver.session() as session:
            if entity_type:
                query = f"MATCH (n:{entity_type} {{name: $name}}) RETURN COUNT(n) > 0 AS exists"
            else:
                query = "MATCH (n {name: $name}) RETURN COUNT(n) > 0 AS exists"
            result = session.run(query, name=entity_name)
            return 

    
    def create_node(self, entity_name, entity_type=None):
        if self.entity_exists(entity_name, entity_type):
            return
        else:
            with self.driver.session() as session:
                if entity_type:
                    query = f"CREATE (n:{entity_type} {{name: $name}})"
                else:
                    query = "CREATE (n {name: $name})"
                session.run(query, name=entity_name)

    
    def relationship_exists(self, entity1_name, relation_type, entity2_name):
        with self.driver.session() as session:
            query = f"""
            MATCH (a {{name: $entity1_name}})-[r:{relation_type}]->(b {{name: $entity2_name}})
            RETURN COUNT(r) > 0 AS exists
            """
            result = session.run(query, entity1_name=entity1_name, entity2_name=entity2_name)
            return 
    
    def create_relationship(self, entity1_name, relation_type, entity2_name, properties=None):
        if self.relationship_exists(entity1_name, relation_type, entity2_name):
            return  # Relationship already exists
        with self.driver.session() as session:
            if properties:
                props = ', '.join([f"{key}: ${key}" for key in properties.keys()])
                query = f"""
                MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                CREATE (a)-[:{relation_type} {{{props}}}]->(b)
                """
            else:
                query = f"""
                MATCH (a {{name: $entity1_name}}), (b {{name: $entity2_name}})
                CREATE (a)-[:{relation_type}]->(b)
                """
            session.run(query, entity1_name=entity1_name, entity2_name=entity2_name, **(properties or {}))


if __name__ == "__main__":
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "password"
    
    neo4j_handler = Neo4jHandler(uri, user, password)

    for d in tqdm(data):
        knowledge = d['knowledge'].replace('/', '_')
        entities = d['entities']
        relation = d['relation']
        if knowledge != '':
            neo4j_handler.create_node(knowledge, "knowledge")
        for entitie in entities:
            entity_name = entitie['entity'].replace('/', '_')
            entity_type = entitie['type'].replace('/', '_')
            description = entitie['description'].replace('/', '_')
    
            neo4j_handler.create_node(entity_name=entity_name, entity_type=entity_type)
            neo4j_handler.create_node(description)
            if entity_name and description:
                neo4j_handler.create_relationship(entity1_name=entity_name, relation_type='description', entity2_name=description)
    
            if knowledge != '' and entity_name and knowledge:
                neo4j_handler.create_relationship(entity1_name=entity_name, relation_type='knowledge', entity2_name=knowledge)
    
        for rela in relation:
            if rela['entity1']:
                entity1 = rela['entity1'].replace('/', '_')
            if rela['entity2']:
                if type(rela['entity2']) == 'list':
                    entity2 = [item.replace('/', '_') for item in rela['entity2']]
                else:
                    entity2 = rela['entity2'].replace('/', '_')
    
            neo4j_handler.create_node(entity1)
            neo4j_handler.create_node(entity2)
            if entity1 and entity2 and rela['relation']:
                if type(rela['entity2']) == 'list':
                    for e2 in rela['entity2']:
                        neo4j_handler.create_relationship(entity1_name=entity1, relation_type='relation', entity2_name=e2, properties={'relation': rela['relation']})
                else:
                    neo4j_handler.create_relationship(entity1_name=entity1, relation_type='relation', entity2_name=entity2, properties={'relation': rela['relation']})



















                