from abc import *

import logging
from copy import deepcopy
from fnmatch import fnmatch

log = logging.getLogger(__name__)
from cel import evaluate, Context

from pyprospector.block import Block


class Filter(Block):
    def __init__(self, filter_dict):
        super().__init__(filter_dict)
        self._type = 'filter'
        self._kind = filter_dict['kind']
        self._title = filter_dict['title']
        self._result = None

    @abstractmethod
    def __call__(self, *args, **kwargs):
        pass


class CELFilter(Filter):
    def __init__(self, filter_dict):
        super().__init__(filter_dict)
        self._parameters = filter_dict.get('parameters', {})
        self._expression = filter_dict['properties']['expression']
        self._arguments = filter_dict['properties'].get('arguments', {})

    def __call__(self, *args, **kwargs):
        log.info(f"Calling {self.__class__}: {self._expression}")
        args = {}
        for arg, value in self._arguments.items():
            if type(value) is str and value.startswith('$'):
                index = int(value[1:])
                args[arg] = self._sources[index-1]._result
            else:
                args[arg] = value

        log.debug(f"Evaluate with {repr({'arguments': args})}")
        context = Context()
        for n, f in FUNCTIONS.items():
            context.add_function(n, f)
        context.update({'arguments': args})
        self._result = evaluate(self._expression, context)


def _cel_sysctl_has_value(entries: dict, key: list) -> list:
    found = []
    for entry in entries['variables']:
        if fnmatch(entry['variable'], key) and key not in entry['exclude']:
            found.append(entry)
    return found

def _cel_audit_has_rule(entries: list, fields: list) -> list:
    found = []
    for e in entries:
        res = True
        for f in fields:
            if type(f) == list:
                one_of = False
                for alt_f in f:
                    one_of = one_of or alt_f in e['fields']
                if not one_of:
                    res = False
            else:
                if f not in e['fields']:
                    res = False
        #print("***", repr(e['fields']), repr(fields), repr(res))
        if res:
           found.append(e)
    return found

def _cel_content_collate(entries: list) -> list:
    for i, f in enumerate(entries):
        for k, v in entries[len(entries)-i-1]['content'].items():
            for j in range(len(entries)-i-2):
                entries[j]['content'].pop(k, None)
    return entries


FILTERS = {
    'cel': CELFilter,
}

FUNCTIONS = {
    'audit_has_rule': _cel_audit_has_rule,
    'sysctl_has_value': _cel_sysctl_has_value,
    'content_collate': _cel_content_collate,
}

def create_filter_from_dict(filter_dict):
    if 'kind' not in filter_dict:
        raise ValueError('The filter definition does not define the kind.')
    return FILTERS[filter_dict['kind']](filter_dict)