import unittest
import tempfile
import shutil
import os
from bluespecrepl import pyverilator

class TestPyVerilator(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.old_dir)
        shutil.rmtree(self.test_dir)

    def test_pyverilator(self):
        test_verilog = '''
            module width_test (
                    input_a,
                    input_b,
                    input_c,
                    input_d,
                    input_e,
                    output_concat);
                input [7:0] input_a;
                input [15:0] input_b;
                input [31:0] input_c;
                input [63:0] input_d;
                input [127:0] input_e;
                output [247:0] output_concat;
                assign output_concat = {input_a, input_b, input_c, input_d, input_e};
            endmodule'''
        # write test verilog file
        with open('width_test.v', 'w') as f:
            f.write(test_verilog)
        test_pyverilator = pyverilator.PyVerilator.build('width_test.v')

        test_pyverilator.start_vcd_trace('test.vcd')
        test_pyverilator['input_a'] = 0xaa
        test_pyverilator['input_b'] = 0x1bbb
        test_pyverilator['input_c'] = 0x3ccccccc
        test_pyverilator['input_d'] = 0x7ddddddddddddddd
        test_pyverilator['input_e'] = 0xfeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee

        self.assertEqual(test_pyverilator['output_concat'], 0xaa1bbb3ccccccc7dddddddddddddddfeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee)

        test_pyverilator.stop_vcd_trace()
