from neo4j import GraphDatabase


class Neo4jEntityFetcher:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    # 获取所有实体（节点）
    def get_all_entities(self):
        with self.driver.session() as session:
            query = "MATCH (n) RETURN n"
            result = session.run(query)
            # 将实体的属性存入列表
            entities = [
                {"id": record["n"].element_id, "labels": list(record["n"].labels), "properties": dict(record["n"])} for
                record in result]
            return entities

    # 获取指定标签的实体
    def get_entities_by_label(self, label):
        with self.driver.session() as session:
            query = f"MATCH (n:{label}) RETURN n"
            result = session.run(query)
            # 将实体的属性存入列表
            entities = [
                {"id": record["n"].element_id, "labels": list(record["n"].labels), "properties": dict(record["n"])} for
                record in result]
            return entities

    # 获取指定属性的实体
    def get_entities_by_property(self, property_name, property_value):
        with self.driver.session() as session:
            query = f"MATCH (n {{{property_name}: '{property_value}'}}) RETURN n"
            result = session.run(query)
            # 将实体的属性存入列表
            entities = [
                {"id": record["n"].element_id, "labels": list(record["n"].labels), "properties": dict(record["n"])} for
                record in result]
            return entities

    # 根据 ID 获取实体
    def get_entity_by_id(self, element_id):
        with self.driver.session() as session:
            query = "MATCH (n) WHERE elementId(n) = $element_id RETURN n"
            result = session.run(query, element_id=element_id)
            # 获取实体的属性
            entity = [
                {"id": record["n"].element_id, "labels": list(record["n"].labels), "properties": dict(record["n"])} for
                record in result]
            return entity

    def get_entities_by_knowledge_id(self, element_id):
        with self.driver.session() as session:
            query = "MATCH (m)-[r]->(n) WHERE elementId(n) = $element_id RETURN m, r"
            result = session.run(query, element_id=element_id)
            entity = [
                {"id": record["m"].element_id, "labels": list(record["m"].labels), "properties": dict(record["m"])} for
                record in result]
            return entity

    def get_entities_by_entities_id(self, element_id):
        with self.driver.session() as session:
            query = "MATCH (n)-[r]->(m) WHERE elementId(n) = $element_id RETURN n, r, m"
            result = session.run(query, element_id=element_id)
            entity = [
                {
                    "key": dict(record["n"])['name'],
                    "id": record["m"].element_id[0],
                    "labels": list(record["m"].labels)[0],
                    "properties": dict(record["m"])['name'],
                    "relationship": {
                        "type": record["r"].type,
                        "properties": dict(record["r"])
                    }
                } for record in result
            ]
            return entity

    # 关闭驱动
    def close(self):
        self.driver.close()


# 初始化 Neo4jEntityFetcher
uri = "bolt://localhost:7687"  # Neo4j 数据库地址
user = "neo4j"  # Neo4j 用户名
password = "password"  # Neo4j 密码
fetcher = Neo4jEntityFetcher(uri, user, password)

# 获取所有实体
# print("所有实体：")
all_entities = fetcher.get_all_entities()

# 根据标签获取实体
# print("\n标签为 'knowledge' 的实体：")
knowledge_entities = fetcher.get_entities_by_label("knowledge")

# 根据属性获取实体
# print("\n具有 name='糖尿病' 属性的实体：")
diabetes_entities = fetcher.get_entities_by_property("name", "糖尿病")

# 关闭连接
fetcher.close()

if __name__ == "__main__":
    # 初始化 Neo4jEntityFetcher
    uri = "bolt://localhost:7687"  # Neo4j 数据库地址
    user = "neo4j"  # Neo4j 用户名
    password = "password"  # Neo4j 密码
    fetcher = Neo4jEntityFetcher(uri, user, password)

    # 获取所有实体
    # print("所有实体：")
    all_entities = fetcher.get_all_entities()

    # 根据标签获取实体
    # print("\n标签为 'knowledge' 的实体：")
    knowledge_entities = fetcher.get_entities_by_label("knowledge")

    # 根据属性获取实体
    # print("\n具有 name='糖尿病' 属性的实体：")
    diabetes_entities = fetcher.get_entities_by_property("name", "糖尿病")

    # 关闭连接
    fetcher.close()
