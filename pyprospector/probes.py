import configparser
import json
import os.path
import typing
from abc import *
from contextlib import contextmanager

import logging
from fnmatch import fnmatch

log = logging.getLogger(__name__)
import subprocess
import re

from pyprospector.block import Block


class Wrapper:
    def __init__(self, tpe, params: dict):
        self._params = params
        self._type = tpe

    @classmethod
    def create_from_dict(cls, wrapper_dict: dict):
        wrapper_type, params = wrapper_dict.popitem()
        return WRAPPERS.get(wrapper_type)(wrapper_type, params)

    @abstractmethod
    def wrap_file(self, f: typing.TextIO):
        pass

    @abstractmethod
    def wrap_string(self, string: str):
        pass

    def __iter__(self):
        for p, v in self._params.items():
            yield p, v

    def __str__(self):
        return self._type


class KeyValue(Wrapper):
    def __init__(self, tpe, params: dict):
        super().__init__(tpe, params)
        self._delimiter = params.get('delimiter', "=")
        self._quotes = params.get('quotes', '\'\"')
        self._ignore_prefixes = params.get('ignore_prefixes', ['#'])
        self._trim_whitespace = params.get('trim_whitespace', True)

    def wrap_file(self, f: typing.IO):
        res = {}
        for l in f.readlines():
            kv = self.wrap_line(l)
            if kv is not None:
                res[kv[0]] = kv[1]
        return res

    def wrap_string(self, string: str):
        # FIXME: Implement
        pass

    def _has_ignored_prefix(self, string: str) -> bool:
        for prefix in self._ignore_prefixes:
            if string.startswith(prefix):
                return True
        return False

    def wrap_line(self, string: str) -> (str, str):
        string = string.strip(' \n')
        if not string:
            return None

        if self._has_ignored_prefix(string):
            return None

        if self._delimiter not in string:
            # TODO: mark invalid line
            return None

        key, value = string.split(self._delimiter, 1)
        key = key.strip(self._quotes)
        value = value.strip(self._quotes)
        if self._trim_whitespace:
            key = key.strip(' ')
            value = value.strip(' ')

        return key, value


class INI(Wrapper):
    def __init__(self, tpe, params: dict):
        super().__init__(tpe, params)

    def wrap_file(self, f: typing.IO):
        config = configparser.ConfigParser()
        config.read_file(f)
        result = {}
        for section in config.sections():
            result[section] = {}
            for k, v in config[section].items():
                result[section][k] = v
        return result

    def wrap_string(self, string: str):
        # FIXME: Implement
        pass


class RegEx(Wrapper):
    def __init__(self, tpe, params: dict):
        super().__init__(tpe, params)
        self._expression = params['expression']
        self._plain = params.get('plain', False)
        self._flags = re.MULTILINE #re.NOFLAG
        flags = params.get('flags', '').lower()
        if 'm' in flags:
            self._flags |= re.MULTILINE
        if 's' in flags:
            self._flags |= re.DOTALL

    def wrap_file(self, f: typing.TextIO):
        content = f.read()
        return list(self.wrap_line(content))

    def wrap_string(self, string: str):
        log.debug(f"Wrapping (string) with Regex expression '{self._expression}'")
        return list(self.wrap_line(string))

    def wrap_line(self, string: str):
        for m in re.finditer(self._expression, string, self._flags):
            if not self._plain:
                d = m.groupdict()
                # FIXME: The CEL implementation fails to import None values into the context
                yield dict(map(lambda kv: (kv[0], '' if kv[1] is None else kv[1]), d.items()))
            else:
                d = m.groups()
                for i in d:
                    yield i


class JsonSeq(Wrapper):
    def __init__(self, tpe, params: dict):
        super().__init__(tpe, params)
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
        return json.loads(string) if string else []


class Probe(Block):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._type = 'probe'
        self._kind = probe_dict['kind']
        self._title = probe_dict['title']
        self._sudo = probe_dict.get('sudo', False)
        self._encoding = probe_dict.get('encoding', None)
        self._result = None
        self._error = None
        self._executor = None

    @abstractmethod
    def __call__(self, *args, **kwargs):
        pass

    @contextmanager
    def _exec(self, cmd: list, encoding=None):
        if self._executor is not None:
            proc = self._executor.exec(cmd, encoding, self._sudo)
            yield proc
        else:
            log.debug(f"Calling command: {' '.join(cmd)}")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, text=True, encoding=encoding)
            yield proc

    @contextmanager
    def _open(self, fn: str):
        with self._exec(['/usr/bin/cat', fn]) as proc:
            res = proc.stdout
            yield res

    def _glob(self, paths: list[str]) -> list[str]:
        # FIXME: Bash-specific
        #paths_gen = "\"compgen -G '" + ' '.join(paths) + "'\""
        paths_gen = "compgen -G '" + ' '.join(paths) + "'"
        with self._exec(['/usr/bin/sh', '-c', paths_gen]) as proc:
            for line in proc.stdout.readlines():
                log.debug(f"Glob line: {line}")
                yield str.strip(line)


class FileContentProbe(Wrappable, Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._parameters = probe_dict.get('parameters', {})
        self._paths = probe_dict['properties']['paths']

    def __call__(self, executor=None, *args, **kwargs):
        self._executor = executor
        log.debug(f"Calling {self.__class__}: {self._paths}")

        res = []
        for path in self._paths:
            for fn in sorted(self._glob([path])):
                with self._open(fn) as f:
                    log.debug(f"Opened file '{fn}'")
                    res.append({
                        'file': fn,
                        'content': self._wrap_file(f)
                    })

        self._result = res
        log.debug(f"{self.__class__} result, output: {res}")

    def get_result_id(self):
        return str(self.__class__) + repr(self._parameters) + repr(self._properties)


class INIFileContentProbe(Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._parameters = probe_dict.get('parameters', {})
        self._paths = probe_dict['properties']['paths']

    def __call__(self, executor=None, *args, **kwargs):
        self._executor = executor
        log.debug(f"Calling {self.__class__}: {self._paths}")

        files = []
        config_res = configparser.ConfigParser(defaults={})
        for path in self._paths:
            for fn in self._glob(path):
                with self._open(fn) as f:
                    config = configparser.ConfigParser()
                    config.read_file(f)
                    result = {}
                    for section in config.sections():
                        result[section] = {}
                        for k, v in config[section].items():
                            result[section][k] = v
                    config_res.read_dict(result)

                    files.append({
                        'file': fn,
                        'content': result
                    })

        result_res = {}
        for section in config_res.sections():
            result_res[section] = {}
            for k, v in config_res[section].items():
                result_res[section][k] = v

        self._result = {
            'files': files,
            'result': result_res
        }
        log.debug(f"{self.__class__} result: {result_res}")

    def get_result_id(self):
        return str(self.__class__) + repr(self._parameters) + repr(self._properties)


class AuditDRuleFileContentProbe(Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._path = probe_dict['properties']['path']

    def _get_rule_element_pairs(self, rule_string: str):
        rl = rule_string.split(' ')
        # FIXME: Do we need to add a None or '' to even-out the list?
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

    def _read_rules(self, f: typing.TextIO, fn: str, result: dict):
        l_no = 0
        for line in f.readlines():
            l_no += 1
            if line.startswith("#"):
                continue
            l = line.strip()
            if not l:
                continue

            if l == '-D':
                self._mark_rules_as_deleted(result['rules'], f'{fn}:{l_no}')
                continue

            lp = self._get_rule_element_pairs(l)

            rule = self._make_rule(lp, f'{fn}:{l_no}')

            syscal_pos = l.find(' -S')
            arch_pos = l.find(' -F arch=')
            if syscal_pos>=0 and arch_pos>=0:
                if arch_pos > syscal_pos:
                    rule['status'] = {'correct': False,
                                      'problem': {'field': '-S precedes -F arch=',
                                                  'file': f'{fn}:{l_no}'}}

            if lp[0].startswith('-a '):
                result['rules'].append(rule)
                continue
            if lp[0].startswith('-A '):
                result['rules'].prepend(rule)
                continue

            result['config'].append(lp)

    def __call__(self, executor=None, *args, **kwargs):
        self._executor = executor
        log.debug(f"Calling {self.__class__}: {self._path}")

        res = {
            'rules': [],
            'config': []
        }
        for fn in sorted(self._glob([self._path])):
            log.debug(f"Loading file '{fn}'")
            with self._open(fn) as f:
                self._read_rules(f, fn, res)

        self._result = res


class SysctlDFileContentProbe(Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        #self._paths = [
        #    "/usr/lib/sysctl.d/*.conf",
        #    "/usr/local/lib/sysctl.d/*.conf",
        #    "/run/sysctl.d/*.conf",
        #    "/etc/sysctl.d/*.conf",
        #    "/etc/sysctl.conf"
        #]
        self._path = probe_dict['properties']['path']

    def _normalize_key(self, key: str) -> str:
        slash_pos = key.find('/')
        dot_pos = key.find('.')
        if (-1 < slash_pos and -1 < dot_pos < slash_pos) or (-1 == slash_pos and -1 < dot_pos):
            return key.translate(str.maketrans('./', '/.'))
        return key

    def _exclude_from_glob(self, res, variable):
        for r in res['variables']:
            if fnmatch(variable, r['variable']):
                if variable not in r['exclude']:
                    r['exclude'].append(variable)

    def _read_variables(self, f, fn, res):
        l_no = 0
        for line in f.readlines():
            l_no += 1
            line = line.strip(' \n')
            if not line or line.startswith('#'):
                continue

            silent = False
            if line.startswith('-'):
                line = line[1:]
                if '=' not in line:
                    self._exclude_from_glob(res, self._normalize_key(line))
                    continue
                silent = True

            variable, value = map(str.strip, line.split('=', 1))

            entry = {
                'variable': self._normalize_key(variable),
                'value': value,
                'silent': silent,
                'file': f'{fn}:{l_no}',
                'exclude': [],
            }

            res['variables'].append(entry)

    def _build_conf_set(self, confs, fn):
        bn = '/' + os.path.basename(fn)
        confs = [conf for conf in confs if not conf.endswith(bn)] + [fn]
        return confs

    def __call__(self, executor=None, *args, **kwargs):
        self._executor = executor
        log.debug(f"Calling {self.__class__}: {self._path}")

        res = {
            'variables': []
        }

        confs = []
        for globs in self._path:
            for fn in sorted(self._glob([globs])):
                confs = self._build_conf_set(confs, fn)

        for fn in confs:
            log.debug(f"Loading file '{fn}'")
            with self._open(fn) as f:
                self._read_variables(f, fn, res)

        self._result = res


class ProcessOutputProbe(Wrappable, Probe):
    def __init__(self, probe_dict):
        super().__init__(probe_dict)
        self._parameters = probe_dict.get('parameters', {})
        self._executable = probe_dict['properties']['executable']
        self._arguments = probe_dict['properties']['arguments']
        self._rc_ok = probe_dict['properties'].get('rc_ok', [0])
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
            if f'${src_i + 1}' in self._arguments:
                i = self._arguments.index(f'${src_i + 1}')
                self._arguments.pop(i)
                l = src._result
                l.reverse()
                for res_el in l:
                    self._arguments.insert(i, str(res_el))

    def __call__(self, executor=None, *args, **kwargs):
        self._executor = executor
        log.debug(f"Calling {self.__class__}: {self._executable} {repr(self._arguments)}")

        self.resolve_source_parameters()

        cmd = [self._executable] + self._arguments

        # log.info(f"Command: {' '.join(cmd)}")
        with self._exec(cmd, encoding=self._encoding) as proc:
            proc_stdout, proc_stderr = proc.communicate(None)
            rc = proc.returncode
            log.debug(f"{self.__class__} return code, err: {rc}, {proc_stderr}")
            log.debug(f"{self.__class__} output: {rc}, {proc_stdout}")
            if rc not in self._rc_ok:
                self._error = {
                    'result': True,
                    'return_code': rc,
                    'stderr': proc_stderr,
                    'stdout': proc_stdout,
                    'findings': None
                }
                self._result = None
            else:
                self._result = self._wrap_string(proc_stdout)
                self._error = None

    def get_result_id(self):
        return str(self.__class__) + repr(self._parameters) + repr(self._properties)


PROBES = {
    'file_content': FileContentProbe,
    'process_output': ProcessOutputProbe,
    'audit_rule_file_content': AuditDRuleFileContentProbe,
    'sysctl_file_content': SysctlDFileContentProbe,
    'ini_file_content': INIFileContentProbe,
}

WRAPPERS = {
    'regex': RegEx,
    'json_seq': JsonSeq,
    'key_value': KeyValue,
    'ini': INI,
}

def create_probe_from_dict(probe_dict):
    if 'kind' not in probe_dict:
        raise ValueError('The probe definition does not define the kind.')
    return PROBES[probe_dict['kind']](probe_dict)