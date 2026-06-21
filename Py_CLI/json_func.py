import json
def read_jfile(file_name: str):
    if "." not in file_name: file_name += ".json"
    with open(file_name, "r") as file:
        try:
            data = json.load(file)
            return data
        except Exception:
            raise Exception("Error opening file")

def write_jfile(file_name: str, data):
    if "." not in file_name: file_name += ".json"
    with open(file_name, "w") as file:
        json.dump(data, file, indent=4)
    return 0
