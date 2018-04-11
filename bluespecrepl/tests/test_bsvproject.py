import unittest
import tempfile
import shutil
import os
from bluespecrepl import bsvproject

class TestBSVProject(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.old_dir)
        shutil.rmtree(self.test_dir)

    def test_bsvproject_init(self):
        with open('Test.bsv', 'w') as f:
            f.write('''
                module mkTest(Empty);
                endmodule
                ''')
        proj = bsvproject.BSVProject(top_file = 'Test.bsv', top_module = 'mkTest')

        proj.compile_verilog()
        # check for verilog output
        self.assertTrue(os.path.isfile(os.path.join('verilog_dir','mkTest.v')))

        proj.compile_bluesim()
        # check for bluesim output
        self.assertTrue(os.path.isfile(os.path.join('sim_dir','mkTest.cxx')))
        self.assertTrue(os.path.isfile('sim.out'))

        proj.gen_python_repl()
        # check for verilator output
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','mkTest.v')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','pyverilator_wrapper.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest')))

        proj.clean()
        # check for verilog output
        self.assertFalse(os.path.isfile(os.path.join('verilog_dir','mkTest.v')))
        # check for bluesim output
        self.assertFalse(os.path.isfile(os.path.join('sim_dir','mkTest.cxx')))
        self.assertFalse(os.path.isfile('sim.out'))

    def test_bsvproject_one_rule(self):
        with open('Test.bsv', 'w') as f:
            f.write('''
                module mkTest(Empty);
                    rule oneRule;
                        $display("Hello, World!");
                    endrule
                endmodule
                ''')
        proj = bsvproject.BSVProject(top_file = 'Test.bsv', top_module = 'mkTest')

        proj.gen_python_repl(scheduling_control = True)
        # check for verilator output
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','mkTest.v')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','pyverilator_wrapper.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest')))

        proj.clean()
        # check for verilog output
        self.assertFalse(os.path.isfile(os.path.join('verilog_dir','mkTest.v')))
        # check for bluesim output
        self.assertFalse(os.path.isfile(os.path.join('sim_dir','mkTest.cxx')))
        self.assertFalse(os.path.isfile('sim.out'))

    def test_bsvproject_two_rules(self):
        with open('Test.bsv', 'w') as f:
            f.write('''
                module mkTest(Empty);
                    rule ruleOne;
                        $display("Hello,");
                    endrule
                    rule ruleTwo;
                        $display("World!");
                    endrule
                endmodule
                ''')
        proj = bsvproject.BSVProject(top_file = 'Test.bsv', top_module = 'mkTest')

        proj.gen_python_repl(scheduling_control = True)
        # check for verilator output
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','mkTest.v')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','pyverilator_wrapper.cpp')))
        self.assertTrue(os.path.isfile(os.path.join('verilator_dir','VmkTest')))

        proj.clean()
        # check for verilog output
        self.assertFalse(os.path.isfile(os.path.join('verilog_dir','mkTest.v')))
        # check for bluesim output
        self.assertFalse(os.path.isfile(os.path.join('sim_dir','mkTest.cxx')))
        self.assertFalse(os.path.isfile('sim.out'))
