import unittest

from bluespecrepl import bsvutil

class TestBSVUtil(unittest.TestCase):
    def test_add_line_macro(self):
        # This test will get messed up if you change the line number
        out = bsvutil.add_line_macro('typedef enum { Yes, No } YesNo deriving (Bits, Eq, FShow);')
        self.assertTrue(out.startswith('`line 8 "%s" 0' % __file__))

        out = bsvutil.add_line_macro('''
        typedef enum { Yes, No } YesNo deriving (Bits, Eq, FShow);
        ''')
        self.assertTrue(out.startswith('`line 11 "%s" 0\n' % __file__))

        out = bsvutil.add_line_macro('', file_name='MyFile.bsv', line_number=10)
        self.assertTrue(out.startswith('`line 10 "MyFile.bsv" 0'))
