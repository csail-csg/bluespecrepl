import unittest
import tempfile
import shutil
import os
from bluespecrepl import bsvproject

class TestPyVerilatorBSV(unittest.TestCase):
    def setUp(self):
        self.old_dir = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.old_dir)
        shutil.rmtree(self.test_dir)

    def test_pyverilatorbsv_nested_interfaces(self):
        with open('IncrementerServer.bsv', 'w') as f:
            f.write('''
                import FIFO::*;
                import ClientServer::*;
                import GetPut::*;

                (* synthesize *)
                module mkIncrementerServer(Server#(Bit#(7), Bit#(7)));
                    FIFO#(Bit#(7)) fifo_in <- mkFIFO;
                    FIFO#(Bit#(7)) fifo_out <- mkFIFO;

                    rule doIncrement;
                        let x = fifo_in.first;
                        fifo_in.deq;
                        fifo_out.enq(x + 1);
                    endrule

                    interface Put request;
                        method Action put(Bit#(7) x);
                            fifo_in.enq(x);
                        endmethod
                    endinterface

                    interface Get response;
                        method ActionValue#(Bit#(7)) get();
                            fifo_out.deq;
                            return fifo_out.first;
                        endmethod
                    endinterface
                endmodule
                ''')
        proj = bsvproject.BSVProject(top_file = 'IncrementerServer.bsv', top_module = 'mkIncrementerServer')

        sim = proj.gen_python_repl(scheduling_control = True)

        sim.io.RST_N = 0
        sim.clock.tick()
        sim.io.RST_N = 1

        self.assertTrue(sim.interface.request.put.ready)
        self.assertFalse(sim.interface.response.get.ready)

        sim.clock.tick()

        self.assertTrue(sim.interface.request.put.ready)
        self.assertFalse(sim.interface.response.get.ready)

        sim.interface.request.put(17)

        sim.rules.doIncrement()
        resp = sim.interface.response.get()

        self.assertEqual(resp, 18)
        self.assertFalse(sim.interface.response.get.ready)
