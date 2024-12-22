import json
import typing
from abc import *
from contextlib import contextmanager

import logging

log = logging.getLogger(__name__)
import subprocess
import glob
import re

from pyprospector.block import Block


class Wrapper:
    @classmethod
    def create_from_dict(cls, wrapper_dict: dict):
        wrapper_type, params = wrapper_dict.popitem()
        return WRAPPERS.get(wrapper_type)(params)

    @abstractmethod
    def wrap_file(self, f: typing.TextIO):
        pass

    @abstractmethod
    def wrap_string(self, string: str):
        pass


class KeyValue(Wrapper):
    def __init__(self, params: dict):
        self._delimiter = params.get('delimiter', "=")
        self._quotes = params.get('quotes', '\'\"')
        self._ignore_prefixes = params.get('ignore_prefixes', ['#'])
        self._trim_whitespace = params.get('trim_whitespace', True)

    def wrap_file(self, f: typing.IO):
        content = f.read()
        return dict(self.wrap_line(content))

    def wrap_string(self, string: str):
        # FIXME: Implement
        pass

    def _has_ignored_prefix(self, string: str) -> bool:
        for prefix in self._ignore_prefixes:
            if string.startswith(prefix):
                return True
        return False

    def wrap_line(self, string: str):
        # FIXME: Balanced (?<=(["']\b))(?:(?=(\\?))\2.)*?(?=\1)
        kv = rf"[^{re.escape(self._quotes)}]*?" if self._quotes else rf"[^\s{re.escape(self._delimiter)}]+?"
        quo = rf"[{re.escape(self._quotes)}]*" if self._quotes else ''
        pattern = (rf"^{'\s*?' if self._trim_whitespace else ''}"
                   rf"{quo}(?P<key>{kv}){quo}"
                   rf"\s*?{re.escape(self._delimiter)}\s*?"
                   rf"{quo}(?P<value>{kv}){quo}"
                   rf"{'\s*?' if self._trim_whitespace else ''}$")
        log.info(f"Wrapping (string/key-value) with Regex expression '{pattern}'")
        for m in re.finditer(pattern, string, re.MULTILINE):
            d = m.groupdict()
            if self._has_ignored_prefix(d['key']):
                continue
            yield d['key'], d['value']


class RegEx(Wrapper):
    def __init__(self, params: dict):
        self._expression = params['expression']
        self._flags = re.MULTILINE
        flags = params.get('flags', '').lower()
        if 'm' in flags:
            self._flags |= re.MULTILINE
        if 's' in flags:
            self._flags |= re.DOTALL

    def wrap_file(self, f: typing.TextIO):
        content = f.read()
        return list(self.wrap_line(content))

    def wrap_string(self, string: str):
        log.info(f"Wrapping (string) with Regex expression '{self._expression}'")
        return list(self.wrap_line(string))

    def wrap_line(self, string: str):
        for m in re.finditer(self._expression, string, self._flags):
            d = m.groupdict()
            # FIXME: The CEL implementation fails to import None values into the context
            yield dict(map(lambda kv: (kv[0], '' if kv[1] is None else kv[1]), d.items()))


class JsonSeq(Wrapper):
    def __init__(self, params: dict):
        self._stringify = params.get('stringify', False)

    def wrap_file(self, f: typing.TextIO):
        return [self.wrap_line(line) for line in f.readline() if line.strip()]

    def wrap_string(self, string: str):
        return [self.wrap_line(line) for line in string.splitlines() if line.strip()]

    def wrap_line(self, string: str):
        if self._stringify:
            return f'"{string}"'
        return json.loads(string)


class Wrappable:
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._wrapper = None
        wrapper_dict = probe_dict.get('wrapper', None)
        if wrapper_dict is not None:
            self._wrapper = Wrapper.create_from_dict(wrapper_dict)

    def _wrap_file(self, f: typing.IO):
        if self._wrapper is not None:
            return self._wrapper.wrap_file(f)
        return json.load(f)

    def _wrap_string(self, string: str):
        if self._wrapper is not None:
            return self._wrapper.wrap_string(string)
        return json.loads(string)


class Probe(Block):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._type = 'probe'
        self._title = probe_dict['title']
        self._sudo = probe_dict.get('sudo', False)
        self._result = None
        self._error = None

    @abstractmethod
    def __call__(self, *args, **kwargs):
        pass

    @contextmanager
    def _open(self, fn: str):
        res = None
        if self._sudo:
            cmd = ['/usr/bin/pkexec', '--keep-cwd', '/usr/bin/cat', fn]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
            res = proc.stdout
            yield res
            proc.wait()
        else:
            res = open(fn)
            yield res
            res.close()


class FileContentProbe(Wrappable, Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._parameters = probe_dict.get('parameters', {})
        self._paths = probe_dict['properties']['paths']

    def __call__(self, *args, **kwargs):
        log.info(f"Calling {self.__class__}: {self._paths}")

        res = []
        for path in self._paths:
            for fn in glob.iglob(path):
                with self._open(fn) as f:
                    res.append({
                        'file': fn,
                        'content': self._wrap_file(f)
                    })

        self._result = res
        log.info(f"{self.__class__} result, output: {res}")

    def get_result_id(self):
        return str(self.__class__) + str(self._parameters)


class AuditDRuleFilesContentProbe(Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._path = probe_dict['properties']['path']

    def _get_rule_element_pairs(self, rule_string: str):
        rl = rule_string.split(' ')
        # FIXME: If needed we could add a None or '' to even-out the list
        return [' '.join([k, v]) for k, v in zip(rl[::2], rl[1::2])]

    def _mark_rules_as_deleted(self, rules, origin: str):
        for r in rules:
            r['status'] = {'correct':  False,
                'problem': {
                    'file': origin,
                    'field': '-D'
                }
            }

    def _make_rule(self, pairs: list, origin: str) -> dict:
        la = pairs[0].split(' ')[1]
        if la.startswith('always,') or la.startswith('never,'):
            la = ','.join(reversed(la.split(',')))
        return {
            'origin': {
                'file': origin
            },
            'list_action': la,
            'fields': pairs[1:],
            'status': {
                'correct': True,
            }
        }

    def _read_rules(self, f: typing.TextIO, result: dict):
        l_no = 0
        for line in f.readlines():
            l_no += 1
            if line.startswith("#"):
                continue
            l = line.strip()
            if not l:
                continue

            if l == '-D':
                self._mark_rules_as_deleted(result['rules'], f'{f.name}:{l_no}')
                continue

            lp = self._get_rule_element_pairs(l)

            rule = self._make_rule(lp, f'{f.name}:{l_no}')

            syscal_pos = l.find(' -S')
            arch_pos = l.find(' -F arch=')
            if syscal_pos>=0 and arch_pos>=0:
                if arch_pos > syscal_pos:
                    rule['status'] = {'correct': False,
                                      'problem': {'field': '-S precedes -F arch=',
                                                  'file': f'{f.name}:{l_no}'}}

            if lp[0].startswith('-a '):
                result['rules'].append(rule)
                continue
            if lp[0].startswith('-A '):
                result['rules'].prepend(rule)
                continue

            result['config'].append(lp)

    def __call__(self, *args, **kwargs):
        log.info(f"Calling {self.__class__}: {self._path}")

        res = {
            'rules': [],
            'config': []
        }
        for fn in sorted(glob.glob(self._path)):
            log.info(f"Loading file '{fn}'")
            with self._open(fn) as f:
                self._read_rules(f, res)

        self._result = res


class ProcessOutputProbe(Wrappable, Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._parameters = probe_dict.get('parameters', {})
        self._executable = probe_dict['properties']['executable']
        self._arguments = probe_dict['properties']['arguments']
        self.resolve_parameters()

    def resolve_parameters(self):
        for param in self._parameters.keys():
            if f'${param}' in self._executable:
                self._executable.replace(f'${param}', self._parameters[param])
            if f'$${param}' in self._executable:
                raise ValueError(f'Can\'t array-expand "$${param}" in "executable" property"')

            if f'${param}' in self._arguments:
                i = self._arguments.index(f'${param}')
                self._arguments[i] = self._parameters[param]
            if f'$${param}' in self._arguments:
                i = self._arguments.index(f'$${param}')
                self._arguments.pop(i)
                self._parameters[param].reverse()
                for param_el in self._parameters[param]:
                    self._arguments.insert(i, param_el)

    def resolve_source_parameters(self):
        for src_i, src in enumerate(self._sources):
            if f'@{src_i + 1}' in self._arguments:
                i = self._arguments.index(f'@{src_i + 1}')
                self._arguments.pop(i)
                l = src._result
                l.reverse()
                for res_el in l:
                    self._arguments.insert(i, str(res_el))

    def __call__(self, *args, **kwargs):
        log.info(f"Calling {self.__class__}: {self._executable} {repr(self._arguments)}")

        self.resolve_source_parameters()

        cmd = [self._executable] + self._arguments
        with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, text=True) as proc:
            proc_stdout, proc_stderr = proc.communicate(None)
            rc = proc.returncode
            log.info(f"{self.__class__} return code, output, err: {rc}, '{proc_stdout}', {proc_stderr}")
            self._result = self._wrap_string(proc_stdout)

    def get_result_id(self):
        return str(self.__class__) + str(self._parameters)


PROBES = {
    'file_content': FileContentProbe,
    'process_output': ProcessOutputProbe,
    'audit_rule_files_content': AuditDRuleFilesContentProbe
}

WRAPPERS = {
    'regex': RegEx,
    'json_seq': JsonSeq,
    'key_value': KeyValue,
}

def create_probe_from_dict(probe_dict):
    if 'kind' not in probe_dict:
        raise ValueError('The probe definition does not define the kind.')
    return PROBES[probe_dict['kind']](probe_dict)