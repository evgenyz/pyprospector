import pytest


@pytest.fixture()
def block_filter_cel_true_dict():
    return {
        'id': 'test_cel',
        'title': 'Test CEL filter which responses back {"result": true}',
        'type': 'filter',
        'kind': 'cel',
        'properties': {
            "expression": "{'result': true}"
        }
    }

@pytest.fixture()
def block_filter_cel_result_from_test_po_dict():
    return {
        'id': 'test_cel',
        'title': 'Test CEL filter which responses back the value from {"result": value}',
        'type': 'filter',
        'kind': 'cel',
        'sources': ['test_po'],
        'properties': {
            "expression": "{'result': arguments['objects']['result']}",
            "arguments": {
                'objects': '$1'
            }
        }
    }

@pytest.fixture()
def block_probe_po_echo_true_dict():
    return {
        'id': 'test_po',
        'title': 'Test process_output probe which echoes {"result": true}',
        'type': 'probe',
        'kind': 'process_output',
        'properties': {
            "executable": "/usr/bin/echo",
            "arguments": ['{"result": true}']
        }
    }

@pytest.fixture()
def test_po_echo_cel_result(block_probe_po_echo_true_dict, block_filter_cel_result_from_test_po_dict):
    return {
        'id': 'test_test',
        'title': 'Test test',
        'description': 'Test test description',
        'blocks': [block_probe_po_echo_true_dict, block_filter_cel_result_from_test_po_dict]
    }