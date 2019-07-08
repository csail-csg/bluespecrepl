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

    def test_bsvproject_get_submodules(self):
        with open('Test.bsv', 'w') as f:
            f.write('''
                import FIFO::*;
                (* synthesize *)
                module mkTop(Empty);
                    Empty middle_submod_1 <- mkMiddle;
                    Empty middle_submod_2 <- mkMiddle;
                    rule ruleOne;
                        $display("Hello,");
                    endrule
                    rule ruleTwo;
                        $display("World!");
                    endrule
                endmodule
                (* synthesize *)
                module mkMiddle(Empty);
                    FIFO#(Bit#(32)) fifo <- mkLFIFO;
                    Empty bottom_submod_1 <- mkBottom1;
                    Empty bottom_submod_2 <- mkBottom2;
                    Empty bottom_submod_3 <- mkBottom3;
                endmodule
                (* synthesize *)
                module mkBottom1(Empty);
                endmodule
                (* synthesize *)
                module mkBottom2(Empty);
                    FIFO#(Bit#(32)) fifo <- mkLFIFO;
                endmodule
                (* synthesize *)
                module mkBottom3(Empty);
                    Empty bottom_submod_1 <- mkBottom1;
                endmodule
                ''')
        expected_result = {
            'mkTop' : [('middle_submod_1', 'mkMiddle'), ('middle_submod_2', 'mkMiddle')],
            'mkMiddle' : [('fifo', 'FIFOL1'), ('bottom_submod_1', 'mkBottom1'), ('bottom_submod_2', 'mkBottom2'), ('bottom_submod_3', 'mkBottom3')],
            'mkBottom1' : [],
            'mkBottom2' : [('fifo', 'FIFOL1')],
            'mkBottom3' : [('bottom_submod_1', 'mkBottom1')]
        }
        proj = bsvproject.BSVProject(top_file = 'Test.bsv', top_module = 'mkTop')
        proj.compile_verilog(extra_bsc_args=['-elab'])
        submodules = proj.get_submodules()
        # make sure submodules is a dict:
        self.assertIsInstance(submodules, dict)
        # make sure the keys of the dict are correct:
        for m in submodules:
            self.assertIn(m, expected_result)
        for m in expected_result:
            self.assertIn(m, submodules)
        # make sure the values of the dict are correct
        for m, submodule_pairs in submodules.items():
            self.assertIsInstance(submodule_pairs, tuple)
            for submodule_pair in submodule_pairs:
                self.assertIn(submodule_pair, expected_result[m])
            for submodule_pair in expected_result[m]:
                self.assertIn(submodule_pair, submodule_pairs)