from __future__ import annotations

import copy

from pyprospector.common import CreatableFromJSON


class Block(CreatableFromJSON):
    @classmethod
    def create_from_dict(cls, block_dict):
        block_type = block_dict['type']
        if block_type == 'probe':
            import pyprospector.probes
            return pyprospector.probes.create_probe_from_dict(block_dict)
        elif block_type == 'filter':
            import pyprospector.filters
            return pyprospector.filters.create_filter_from_dict(block_dict)
        raise ValueError(f'Invalid block type "{block_type}", available block types: probe, filter.')

    def __init__(self, block_dict):
        super().__init__(block_dict)
        self._type = None
        self._kind = None
        self._raw_src = copy.deepcopy(block_dict)
        self._sources = block_dict.get('sources', [])
        self._properties = block_dict.get('properties', [])
        self._result = None
        self._elapsed = 0

    def __repr__(self):
        return f'{self.__class__}: {self.id}, sources: {repr(self.sources)}'

    def resolve_sources(self, blocks: list[Block]):
        for i, bid in enumerate(self._sources):
            for block in blocks:
                if block.id == bid:
                    self._sources[i] = block

    def get_result_id(self):
        return None

    @property
    def sources(self):
        return self._sources

    # def get_dependencies(self):
    #    return self._sources
