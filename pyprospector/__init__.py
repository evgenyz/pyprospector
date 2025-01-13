import json
import pathlib
import subprocess

from typing import TextIO

from pyprospector.block import Block
from pyprospector.common import CreatableFromJSON
from pprint import pp
from urllib.parse import urlparse

import logging

from pyprospector.probes import Wrappable

log = logging.getLogger(__name__)


class Test(CreatableFromJSON):
    def __init__(self, test_dict):
        super().__init__(test_dict)
        self._title = test_dict['title']
        self._description = test_dict['description']
        self._blocks = []
        self._result = None
        self._error = None

        for blk_dict in test_dict['blocks']:
            blk = Block.create_from_dict(blk_dict)
            if self.have_blocks(blk.sources):
                self.add_block(blk)
            else:
                raise ValueError(f'Block "{blk.id}" dependencies are not satisfied (reorder blocks in the test)')

    def add_block(self, blk: Block):
        blk.resolve_sources(self._blocks)
        self._blocks.append(blk)

    def have_blocks(self, ids: list[str]):
        found = 0
        for blk in self._blocks:
            if blk.id in ids:
                found += 1
        return found == len(ids)

    def __call__(self, executor=None, *args, **kwargs):
        executor.print(f"Executing test {self.id}: ")
        for blk in self._blocks:
            executor.printnnl(f"--> {blk.id}: ")
            if executor is not None:
                result = executor.get_cached_result(blk)
                if result is not None:
                    blk._result = result
                    self._result = result
                    log.debug(f"Using cached result for {blk.id}")
                    continue
            blk(executor)
            if blk._result is not None:
                self._result = blk._result
                executor.put_cached_result(blk)
                executor.print("OK")
            else:
                self._error = blk._error
                executor.print("ERROR")
                break
        if self._result is not None:
            executor.print(json.dumps(self._result, indent=2))
            executor.print(f"{'XXX FAIL' if self._result['result'] else '=== PASSED' }")
        else:
            executor.print(json.dumps(self._error, indent=2))
            executor.print(f"{'*** ERROR'}")
        executor.print(f"-------------------------------------------------------------")


class Executor:
    def __init__(self, target: str, silent=True):
        self._silent = silent
        self._cache = {}
        self._target = None if not target else urlparse(target)
        log.debug(f"Target {repr(self._target)}")

    def print(self, message: str):
        if not self._silent:
            print(message)

    def printnnl(self, message: str):
        if not self._silent:
            print(message, end='')

    def get_cached_result(self, blk: Block):
        rid = blk.get_result_id()
        log.debug(f"CACHE:GET: Result ID: {rid}")
        if rid is not None:
            result = self._cache.get(rid, None)
            if result is not None:
                log.debug("CACHE:GET: Got cached result!")
                return result

    def put_cached_result(self, blk: Block):
        rid = blk.get_result_id()
        log.debug(f"CACHE:PUT: Result ID: {rid}")
        if rid is not None:
             self._cache[rid] = blk._result

    def __call__(self, *tests: Test, **kwargs):
        for test in tests:
            test(self)

    def exec(self, cmd: list, encoding=None, sudo=False):
        if self._target is not None:
            if self._target.scheme == 'container':
                cmd = ['/usr/bin/podman', 'exec', self._target.netloc] + cmd
            elif self._target.scheme == 'ssh':
                if sudo:
                    cmd = ['sudo'] + cmd
                if cmd[0] == '/usr/bin/sh' and cmd[1] == '-c':
                    # FIXME This is UGLY! Needs better escaping everywhere.
                    cmd = ['/usr/bin/ssh', self._target.netloc] + [' '.join(cmd[:2]) + ' "' + cmd[2] + '"']
                else:
                    cmd = ['/usr/bin/ssh', self._target.netloc] + [' '.join(cmd)]
            else:
                # TODO: We can't be here
                pass
        else:
            if sudo:
                cmd = ['/usr/bin/pkexec', '--keep-cwd'] + cmd

        log.debug(f"Executing command: {' '.join(cmd)}")
        log.debug(f"Executing command (repr): {repr(cmd)}")
        return subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE, text=True, encoding=encoding)


# Croquis
class Plan(CreatableFromJSON):
    @classmethod
    def create_from_files(cls, files: list[pathlib.Path]):
        plan = None
        for fn in files:
            with open(fn, 'r') as f:
                if plan is None:
                    plan = Plan.create_from_file(f)
                else:
                    plan.add_from_file(f)
        return plan

    def __init__(self, plan_dict):
        super().__init__(plan_dict)

        self._tests = []
        self._variables = {}

        # FIXME: this is silly
        if 'tests' in plan_dict:
            self._title = plan_dict['title']
            self._description = plan_dict['description']
            for tst in plan_dict['tests']:
                self._tests.append(Test(tst))
            self._variables.update(plan_dict.get('variables', {}))
        elif 'blocks' in plan_dict:
            self._title = 'None'
            self._description = 'Arbitrary test set.'
            self._tests.append(Test(plan_dict))

    def add_test_from_file(self, f: TextIO):
        self._tests.append(Test.create_from_file(f))

    def drop_other_tests(self, test_id: str):
        self._tests = [test for test in self._tests if test_id == test.id]

    def execute(self, exe: Executor):
        exe(*self._tests)

    def print_results(self):
        for test in self._tests:
            for blk in test._blocks:
                print("-----------------------------------------------------------")
                print(f"- {blk.id} ")
                pp(blk._result)
            else:
                print("///////////////////////////////////////////////////////////")

    def print_json_results(self):
        jd = {
            'id': self.id,
            'title': self._title,
            'tests': []
        }
        for test in self._tests:
            jd['tests'].append({
                'id': test.id,
                'result': test._result #test._blocks[-1]._result
            })
        print(json.dumps(jd, indent=2))

    def write_report(self, f: TextIO):
        f.write('<meta charset="utf-8" emacsmode="-*- markdown -*-"><link rel="stylesheet" href="markdeep.css">\n')

        f.write(f"**{self._title}**\n\n")
        f.write(f"  {self._description}\n\n")

        for test in self._tests:
            f.write(f"{test._title}\n")
            f.write(f"{'='*len(test._title)}\n")

            f.write(f"{test._description}\n\n")

            if test._result is not None:
                if test._result['result']:
                    f.write(f"!!! ERROR: Failed\n")
                    f.write("   <details>\n")
                    f.write("   <summary><b>Findings</b></summary>\n")
                    f.write(f"   ```json\n"
                            f"{json.dumps(test._result['findings'], indent=4)}\n"
                            f"   ```\n")
                    f.write("   </details>\n\n")
                else:
                    f.write(f"!!! TIP\n    Passed\n\n")
            else:
                f.write(f"{'!!! WARNING\n    Error\n\n'}")
                f.write("   <details>\n")
                f.write("   <summary><b>Details</b></summary>\n")
                f.write(f"   ```json\n"
                        f"{json.dumps(test._error, indent=4)}\n"
                        f"   ```\n")
                f.write("   </details>\n\n")


            for blk in test._blocks:
                mark = ""
                f.write(f"{blk._title}\n")
                f.write(f"{'-'*len(blk._title)}\n\n")

                f.write("<details>\n")
                f.write(f"   <summary>**{blk.id}**</summary>\n")
                f.write(f"   ```json\n"
                        f"{json.dumps(blk._raw_src, indent=4)}\n"
                        f"   ```\n")
                f.write("</details>\n\n")

                f.write(f"| **Type/Kind** | **{blk._type}/{blk._kind}** |\n")
                f.write(f"| --- | --- |\n")
                for p, v in blk._properties.items():
                    f.write(f"| {p} | `{v}` |\n")
                if isinstance(blk, Wrappable):
                    f.write(f"| **Wrapper** | {blk._wrapper} |\n")
                    if blk._wrapper is not None:
                        for p, v in blk._wrapper:
                            f.write(f"| {p} | `{v}` |\n")
                f.write("\n")

                if blk._result is not None:
                    f.write("<details>\n")
                    f.write("   <summary><b>Result</b></summary>\n")
                    f.write(f"   ```json\n"
                            f"{json.dumps(blk._result, indent=4)}\n"
                            f"   ```\n")
                    f.write("</details>\n\n")

                if blk._error is not None:
                    f.write("<details>\n")
                    f.write("   <summary><b>Error</b></summary>\n")
                    f.write(f"   ```json\n"
                            f"{json.dumps(blk._error, indent=4)}\n"
                            f"   ```\n")
                    f.write("</details>\n\n")

                if blk._result is None and blk._error is None:
                    f.write("⚠ Skipped\n\n")

        f.write('<!-- Markdeep: -->'
                '<style class="fallback">body{visibility:hidden;white-space:pre;font-family:monospaced}</style>'
                '<script>markdeepOptions={tocStyle:"long"};</script>'
                '<script src="markdeep.min.js"></script>'
                '<script>window.alreadyProcessedMarkdeep||(document.body.style.visibility="visible")</script>')