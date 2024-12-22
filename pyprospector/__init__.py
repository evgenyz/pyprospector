from pyprospector.block import Block
from pyprospector.common import CreatableFromJSON
from pprint import pp

import logging

log = logging.getLogger(__name__)


class Test(CreatableFromJSON):
    def __init__(self, test_dict):
        super().__init__(test_dict)
        self._title = test_dict['title']
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
        self._tests = []
        self._variables = {}
        for tst in plan_dict['tests']:
            self._tests.append(Test(tst))
        self._variables.update(plan_dict.get('variables', {}))

    def execute(self, exe: Executor):
        exe(*self._tests)

    def print_results(self):
        for test in self._tests:
            for block in test._blocks:
                print("-----------------------------------------------------------")
                print(f"- {block.id} ")
                pp(block._result)
            else:
                print("===========================================================")