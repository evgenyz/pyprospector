import json
from abc import *

import logging
from fnmatch import fnmatch

log = logging.getLogger(__name__)
from cel import evaluate, Context
from regopy import Interpreter

from pyprospector.block import Block


class Filter(Block):
    def __init__(self, filter_dict):
        super().__init__(filter_dict)
        self._type = 'filter'
        self._kind = filter_dict['kind']
        self._title = filter_dict['title']
        self._result = None
        self._error = None

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
        log.debug(f"Calling {self.__class__}: {self._expression}")
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


class REGOFilter(Filter):
    def __init__(self, filter_dict):
        super().__init__(filter_dict)
        self._parameters = filter_dict.get('parameters', {})
        self._expression = filter_dict['properties']['expression']
        self._arguments = filter_dict['properties'].get('arguments', {})

    def __call__(self, *args, **kwargs):
        log.debug(f"Calling {self.__class__}: {self._expression}")
        args = {}
        for arg, value in self._arguments.items():
            if type(value) is str and value.startswith('$'):
                index = int(value[1:])
                args[arg] = self._sources[index-1]._result
            else:
                args[arg] = value

        log.debug(f"Evaluate with {repr({'arguments': args})}")

        rego = Interpreter()
        rego.add_data(args)
        q = rego.query(self._expression)
        res = q.binding('result').json()
        self._result = json.loads(res)


def _cel_sysctl_has_value(entries: dict, key: list) -> list:
    found = []
    for entry in entries['variables']:
        if fnmatch(entry['variable'], key) and key not in entry['exclude']:
            found.append(entry)
    return found

def _cel_audit_has_value(entries: dict, key: list) -> list:
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

def _cel_permissions_match(permissions: str, mask: str) -> bool:
    # -rwsr-xr-x, ???s??????
    if len(permissions) != len(mask):
        return False
    for i, s in enumerate(permissions):
        if mask[i] != '?':
            if s != mask[i]:
                return False
    return True

def _cel_mount_options_have(options: str, option: str) -> bool:
    # rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=winnt,errors=remount-ro
    return option in options.split(',')


FILTERS = {
    'cel': CELFilter,
    'rego': REGOFilter,
}

FUNCTIONS = {
    'audit_has_rule': _cel_audit_has_rule,
    'audit_has_value': _cel_audit_has_value,
    'sysctl_has_value': _cel_sysctl_has_value,
    'content_collate': _cel_content_collate,
    'permissions_match': _cel_permissions_match,
    'mount_options_have': _cel_mount_options_have,
}

def create_filter_from_dict(filter_dict):
    if 'kind' not in filter_dict:
        raise ValueError('The filter definition does not define the kind.')
    return FILTERS[filter_dict['kind']](filter_dict)