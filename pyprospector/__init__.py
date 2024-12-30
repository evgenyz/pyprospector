import json
from typing import TextIO

from pyprospector.block import Block
from pyprospector.common import CreatableFromJSON
from pprint import pp

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
        for blk in self._blocks:
            if executor is not None:
                result = executor.get_cached_result(blk)
                if result is not None:
                    blk._result = result
                    self._result = result
                    continue
            blk()
            self._result = blk._result


class Executor:
    def __init__(self):
        self._cache = {}
        pass

    def get_cached_result(self, blk: Block):
        result = self._cache.get(blk.get_result_id(), None)
        if result is not None:
            log.info("Got cached result!")

    def __call__(self, *tests: Test, **kwargs):
        for test in tests:
            test(self)


# Croquis
class Plan(CreatableFromJSON):
    def __init__(self, plan_dict):
        super().__init__(plan_dict)
        self._title = plan_dict['title']
        self._description = plan_dict['description']
        self._tests = []
        self._variables = {}
        for tst in plan_dict['tests']:
            self._tests.append(Test(tst))
        self._variables.update(plan_dict.get('variables', {}))

    def drop_other_tests(self, test_id: str):
        self._tests = [test for test in self._tests if test_id == test.id]

    def execute(self, exe: Executor):
        exe(*self._tests)

    def print_results(self):
        for test in self._tests:
            for block in test._blocks:
                print("-----------------------------------------------------------")
                print(f"- {block.id} ")
                pp(block._result)
            else:
                print("///////////////////////////////////////////////////////////")

    def print_json_results(self):
        jd = {
            'id': self.id,
            'title': self._title,
            'description': self._description,
            'tests': []
        }
        for test in self._tests:
            jd['tests'].append({
                'id': test.id,
                'result': test._blocks[-1]._result
            })
        print(json.dumps(jd, indent=2))

    def write_report(self, f: TextIO):
        f.write('<meta charset="utf-8" emacsmode="-*- markdown -*-"><link rel="stylesheet" href="markdeep.css">\n')

        f.write(f"**Evaluation Report**\n")
        f.write(f"  {self._title}\n\n")
        f.write(f"  {self._description}\n\n")

        for test in self._tests:
            f.write(f"{test._title}\n")
            f.write(f"{'='*len(test._title)}\n")
            f.write(f"{test._description}\n")

            for blk in test._blocks:
                f.write(f"{blk._title}\n")
                f.write(f"{'-'*len(blk._title)}\n\n")

                f.write(f"| ID | {blk.id} |\n")
                f.write(f"| --- | --- |\n")
                f.write(f"| **Type/Kind** | **{blk._type}/{blk._kind}** |\n")
                for p, v in blk._properties.items():
                    f.write(f"| {p} | `{v}` |\n")
                #if isinstance(blk, Wrappable):
                #    f.write(f"| **Wrapper** | |\n")
                #    if blk._wrapper is not None:
                #        for p, v in blk._wrapper:
                #            f.write(f"| {p} | {v.replace("|", "&#124;")} |\n")
                f.write("\n")

                f.write("<details>\n")
                f.write("   <summary><b>Output</b></summary>\n")
                f.write(f"```json\n"
                        f"{json.dumps(blk._result, indent=2)}\n"
                        f"```\n")
                f.write("</details>\n\n")

                f.write("<details>\n")
                f.write("   <summary>Raw source</summary>\n")
                f.write(f"```json\n"
                        f"{json.dumps(blk._raw_src, indent=2)}\n"
                        f"```\n")
                f.write("</details>\n\n")


        f.write('<!-- Markdeep: -->'
                '<style class="fallback">body{visibility:hidden;white-space:pre;font-family:monospaced}</style>'
                '<script>markdeepOptions={tocStyle:"long"};</script>'
                '<script src="markdeep.min.js"></script>'
                '<script>window.alreadyProcessedMarkdeep||(document.body.style.visibility="visible")</script>')