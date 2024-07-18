
import os
import json
from typing import Any, List, Type
from pydantic import BaseModel

DB_DIR = os.path.join(os.environ.get('WORKDIR', '.'), '.db')

class DataStore():
    """ Local data store for storing data in the application
    Persist to local file system
    """

    def __init__(self, name: str, data_model:BaseModel, store_path: str = DB_DIR) -> None:
        self.name = name
        self.table = {}
        self.data_model = data_model
        self.dir_path = f'{store_path}/{name}'

        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        self._reload_table()

    def _reload_table(self) -> None:
        for file in os.listdir(self.dir_path):
            # TODO: detect if dir has changed or not
            file_path = os.path.join(self.dir_path, file)
            if os.path.isfile(file_path) and file.endswith('.json'):
                # file name is the same as item id
                item_id = '.'.join(file.split('.')[:-1])
                with open(file_path, 'r') as f:
                    content = json.load(f)
                    assert content['id'] == item_id
                    self.table[item_id] = self.data_model(**content)


    def get(self, primary_key: str) -> BaseModel:
        item = self.table.get(primary_key, None)
        return item

    def put(self, value: BaseModel) -> None:
        primary_key = value.id
        self.table[primary_key] = value
        with open(f'{self.dir_path}/{primary_key}.json', 'w') as f:
            f.write(value.model_dump_json())

    def scan(self, fn: Any = lambda k, v: True) -> List[BaseModel]:
        self._reload_table()
        
        results = []
        for k, v in self.table.items():
            if fn(k, v):
                results.append(v)
        return results