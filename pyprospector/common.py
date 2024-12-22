import json
from typing import TextIO


class CreatableFromDict:
    @classmethod
    def create_from_dict(cls, obj_dict: dict):
        return cls(obj_dict)

    def __init__(self, obj_dict: dict):
        self._id = obj_dict['id']

    @property
    def id(self):
        return self._id


class CreatableFromJSON(CreatableFromDict):
    @classmethod
    def create_from_string(cls, obj_string: str):
        obj_dict = json.loads(obj_string)
        return cls(obj_dict)

    @classmethod
    def create_from_file_name(cls, file_name: str):
        with open(file_name) as f:
            return cls.create_from_file(f)

    @classmethod
    def create_from_file(cls, f: TextIO):
        obj_dict = json.load(f)
        return cls(obj_dict)
