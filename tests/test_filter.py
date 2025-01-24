from pyprospector.block import Block


def test_cel_filter(block_filter_cel_true_dict):
    p = Block.create_from_dict(block_filter_cel_true_dict)
    assert p is not None
    # FIXME assert p.get_dependencies() == []
    p()
    assert p._result == {'result': True}

def test_cel_filter_map_transform():
    p_dict = {
        'id': 'test_cel',
        'title': '...',
        'type': 'filter',
        'kind': 'cel',
        'properties': {
            "expression": "arguments['objects'].map(el, {'b': el['b'], 'n': arguments['other_objects'].filter(m, el['a'] in m['l'])[0]['n']})",
            "arguments": {
                "objects": [{'a': 1, 'b': 2, 'c': 3}, {'a': 11, 'b': 22, 'c': 33}],
                "other_objects": [{'n': 'N', 'l': [1]}, {'n': "NN", 'l': [11]}]
            }
        }
    }
    p = Block.create_from_dict(p_dict)
    p()
    assert p._result == [{'b': 2, 'n': 'N'}, {'b': 22, 'n': 'NN'}]

def test_rego_filter():
    p_dict = {
        'id': 'test_rego',
        'title': '...',
        'type': 'filter',
        'kind': 'rego',
        'properties': {
            "expression": 'result = {"val": 42}',
            "arguments": {
            }
        }
    }
    p = Block.create_from_dict(p_dict)
    p()
    assert p._result == {"val": 42}

def test_rego_filter_args():
    p_dict = {
        'id': 'test_rego',
        'title': '...',
        'type': 'filter',
        'kind': 'rego',
        'properties': {
            "expression": 'result = {"val": 42, "data.foo": data.foo}',
            "arguments": {
                'foo': 'bar'
            }
        }
    }
    p = Block.create_from_dict(p_dict)
    p()
    assert p._result == {"val": 42, "data.foo": "bar"}

def test_rego_filter_xxx():
    p_dict = {
        'id': 'test_rego',
        'title': '...',
        'type': 'filter',
        'kind': 'rego',
        'properties': {
            "expression": 'result = {"val": 42, "data.foo": data.foo}',
            "arguments": {
                'foo': 'bar'
            }
        }
    }
    p = Block.create_from_dict(p_dict)
    p()
    assert p._result == {"val": 42, "data.foo": "bar"}