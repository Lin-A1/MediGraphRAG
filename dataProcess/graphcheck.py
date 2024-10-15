import json

def validate_json_format(json_data):
    errors = []

    # 检查 "knowledge" 字段
    if "knowledge" not in json_data or not isinstance(json_data["knowledge"], str):
        errors.append(("knowledge", "Missing or invalid 'knowledge' field"))

    # 检查 "entities" 字段
    if "entities" not in json_data or not isinstance(json_data["entities"], list):
        errors.append(("entities", "Missing or invalid 'entities' field"))
    else:
        for index, entity in enumerate(json_data["entities"]):
            missing_keys = [key for key in ["entity", "type", "description"] if key not in entity]
            if missing_keys:
                errors.append((f"entities[{index}]", f"Missing keys: {', '.join(missing_keys)}"))

    # 检查 "relation" 字段
    if "relation" not in json_data or not isinstance(json_data["relation"], list):
        errors.append(("relation", "Missing or invalid 'relation' field"))
    else:
        for index, relation in enumerate(json_data["relation"]):
            missing_keys = [key for key in ["entity1", "relation", "entity2"] if key not in relation]
            if missing_keys:
                errors.append((f"relation[{index}]", f"Missing keys: {', '.join(missing_keys)}"))

    return errors

def check_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 假设 data 是一个 JSON 对象列表
        if not isinstance(data, list):
            print(f"File '{file_path}' is not a valid list of JSON objects.")
            return

        # 验证每个 JSON 对象的格式
        for idx, json_object in enumerate(data):
            errors = validate_json_format(json_object)
            if errors:
                print(f"JSON object at index {idx} is invalid:")
                for field, message in errors:
                    print(f" - {field}: {message}")

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

# 文件路径
json_file_path = "../data/graph.json"

# 检查 JSON 文件
check_json_file(json_file_path)