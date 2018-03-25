import unittest

from bluespecrepl import tclutil

class TestTCLUtil(unittest.TestCase):
    tclstring_repr = 'a b {c {d e} f} {g h}'
    list_repr = ['a', 'b', ['c', ['d', 'e'], 'f'], ['g', 'h']]
    tuple_repr = ('a', 'b', ('c', ('d', 'e'), 'f'), ('g', 'h'))

    def test_tclstring_to_nested_list(self):
        x = tclutil.tclstring_to_nested_list(TestTCLUtil.tclstring_repr)
        self.assertEqual(x, TestTCLUtil.tuple_repr)

    def test_nested_list_to_tclstring(self):
        # This function works on nested lists and nested tuples
        x = tclutil.nested_list_to_tclstring(TestTCLUtil.list_repr)
        self.assertEqual(x, TestTCLUtil.tclstring_repr)
        y = tclutil.nested_list_to_tclstring(TestTCLUtil.tuple_repr)
        self.assertEqual(y, TestTCLUtil.tclstring_repr)
