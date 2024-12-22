from pyprospector import Plan, Executor


def test_plan(test_po_echo_cel_result):
    plan_dict = {
        'id': 'test_plan',
        'title': 'Test plan',
        'variables': {
            'foo': 'bar'
        },
        'tests': [test_po_echo_cel_result]
    }
    p = Plan.create_from_dict(plan_dict)
    assert p is not None

    assert p._variables == {
        'foo': 'bar'
    }

    e = Executor()
    p.execute(e)