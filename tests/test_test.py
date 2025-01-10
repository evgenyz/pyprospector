from pyprospector import Test, Executor

def test_test(test_po_echo_cel_result):
    t = Test.create_from_dict(test_po_echo_cel_result)
    assert t is not None

    assert len(t._blocks) == 2

    e = Executor('')
    e(t)

    assert t._result == {'result': True}

