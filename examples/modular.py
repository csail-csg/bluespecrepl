import os
from bluespecrepl import bsvproject, bsvutil, pyverilatorbsv, bluetcl

# setup build directory
build_dir = os.path.join(os.path.dirname(__file__), 'build', os.path.basename(__file__))
os.makedirs(build_dir, exist_ok = True)
os.chdir(build_dir)

bsv = bsvutil.add_line_macro('''
import FIFO::*;
import MyMiddleModule::*;
import MyInnerModule::*;

(* synthesize *)
module mkMyOuterModule(FIFO#(Bit#(32)));
    FIFO#(Bit#(32)) fifo_1 <- mkLFIFO;
    FIFO#(Bit#(32)) fifo_2 <- mkLFIFO;
    FIFO#(Bit#(32)) submod_1 <- mkMyMiddleModule;
    AltFIFO#(Bit#(32)) submod_2 <- mkAltInnerModule;
    FIFO#(Bit#(32)) submod_3 <- mkMyMiddleModule;
    Empty submod_empty <- mkEmptyInnerModule;

    rule submod_1_to_fifo_1;
        let x = submod_1.first;
        submod_1.deq;

        fifo_1.enq(x);
    endrule

    rule fifo_1_to_submod_2;
        let x = fifo_1.first;
        fifo_1.deq;

        submod_2.enq(x);
    endrule

    rule submod_2_to_fifo_2;
        let x = submod_2.first;
        submod_2.deq;

        fifo_2.enq(x);
    endrule

    rule fifo_2_to_submod_3;
        let x = fifo_2.first;
        fifo_2.deq;

        submod_3.enq(x);
    endrule

    rule submod_2_forward;
        submod_2.forward;
    endrule

    method Action enq(Bit#(32) x);
        submod_1.enq(x);
    endmethod

    method Bit#(32) first;
        return submod_3.first;
    endmethod
    method Action deq;
        submod_3.deq;
    endmethod

    method Action clear;
        submod_1.clear;
        fifo_1.clear;
        submod_2.clear;
        fifo_2.clear;
        submod_3.clear;
    endmethod
endmodule
''')
with open('SubmoduleTest.bsv', 'w') as f:
    f.write(bsv)

bsv = bsvutil.add_line_macro('''
import FIFO::*;
import MyInnerModule::*;

(* synthesize *)
module mkMyMiddleModule(FIFO#(Bit#(32)));
    FIFO#(Bit#(32)) fifo_1 <- mkLFIFO;
    FIFO#(Bit#(32)) fifo_2 <- mkLFIFO;
    FIFO#(Bit#(32)) submod_1 <- mkMyInnerModule;
    FIFO#(Bit#(32)) submod_2 <- mkMyInnerModule;
    FIFO#(Bit#(32)) submod_3 <- mkMyInnerModule;

    rule submod_1_to_fifo_1;
        let x = submod_1.first;
        submod_1.deq;

        fifo_1.enq(x);
    endrule

    rule fifo_1_to_submod_2;
        let x = fifo_1.first;
        fifo_1.deq;

        submod_2.enq(x);
    endrule

    rule submod_2_to_fifo_2;
        let x = submod_2.first;
        submod_2.deq;

        fifo_2.enq(x);
    endrule

    rule fifo_2_to_submod_3;
        let x = fifo_2.first;
        fifo_2.deq;

        submod_3.enq(x);
    endrule

    method Action enq(Bit#(32) x);
        submod_1.enq(x);
    endmethod

    method Bit#(32) first;
        return submod_3.first;
    endmethod
    method Action deq;
        submod_3.deq;
    endmethod

    method Action clear;
        submod_1.clear;
        fifo_1.clear;
        submod_2.clear;
        fifo_2.clear;
        submod_3.clear;
    endmethod
endmodule
''')
with open('MyMiddleModule.bsv', 'w') as f:
    f.write(bsv)

bsv = bsvutil.add_line_macro('''
import FIFO::*;

(* synthesize *)
module mkEmptyInnerModule(Empty);
endmodule

(* synthesize *)
module mkMyInnerModule(FIFO#(Bit#(32)));
    FIFO#(Bit#(32)) fifo_1 <- mkLFIFO;
    FIFO#(Bit#(32)) fifo_2 <- mkLFIFO;

    rule inner_forward;
        let x = fifo_1.first;
        fifo_1.deq;

        fifo_2.enq(x);
    endrule

    method Action enq(Bit#(32) x);
        fifo_1.enq(x);
    endmethod

    method Bit#(32) first;
        return fifo_2.first;
    endmethod
    method Action deq;
        fifo_2.deq;
    endmethod

    method Action clear;
        fifo_1.clear;
        fifo_2.clear;
    endmethod
endmodule

interface AltFIFO#(type t);
    method Action enq(t x);
    method Action deq;
    method t first;
    method Action clear;
    method Action forward;
endinterface

(* synthesize *)
module mkAltInnerModule(AltFIFO#(Bit#(32)));
    FIFO#(Bit#(32)) fifo_1 <- mkLFIFO;
    FIFO#(Bit#(32)) fifo_2 <- mkLFIFO;

    FIFO#(Bit#(32)) fifo_3 <- mkLFIFO;
    FIFO#(Bit#(32)) fifo_4 <- mkLFIFO;

    rule inner_forward_1;
        let x = fifo_1.first;
        fifo_1.deq;

        fifo_2.enq(x);
    endrule

    rule inner_forward_2;
        let x = fifo_3.first;
        fifo_3.deq;

        fifo_4.enq(x);
    endrule

    method Action enq(Bit#(32) x);
        fifo_1.enq(x);
    endmethod

    method Bit#(32) first;
        return fifo_4.first;
    endmethod
    method Action deq;
        fifo_4.deq;
    endmethod

    method Action forward;
        let x = fifo_2.first;
        fifo_2.deq;

        fifo_3.enq(x);
    endmethod

    method Action clear;
        fifo_1.clear;
        fifo_2.clear;
        fifo_3.clear;
        fifo_4.clear;
    endmethod
endmodule

(* synthesize *)
module mkIgnoredModule(FIFO#(Bit#(32)));
    FIFO#(Bit#(32)) fifo <- mkLFIFO;

    method Action enq(Bit#(32) x);
        fifo.enq(x);
    endmethod

    method Bit#(32) first;
        return fifo.first;
    endmethod
    method Action deq;
        fifo.deq;
    endmethod

    method Action clear;
        fifo.clear;
    endmethod
endmodule

(* synthesize *)
module mkUrgencyExample(Empty);
    Reg#(Bool) r <- mkReg(False);
    Reg#(Bit#(32)) x <- mkReg(0);

    rule increment_by_one(r);
        x <= x + 1;
    endrule

    rule increment_by_two;
        x <= x + 2;
    endrule
endmodule
''')
with open('MyInnerModule.bsv', 'w') as f:
    f.write(bsv)

proj = bsvproject.BSVProject('SubmoduleTest.bsv', 'mkMyOuterModule')

sim = proj.gen_python_repl(scheduling_control = True)

# show some basic usage of the repl for a module with submodules
def repl_eval(command):
    print('')
    print('>> ' + command)
    command_result = eval(command)
    if command_result is not None:
        print(repr(command_result))
def repl_exec(command):
    print('')
    command_lines = command.split('\n')
    for i in range(len(command.split('\n'))):
        if i == 0:
            print('>> ' + command_lines[i])
        else:
            print('.. ' + command_lines[i])
    exec(command)

repl_eval('sim')
repl_eval('sim.modular')
repl_eval('sim.modular.submod_2')
repl_eval('sim.interface.enq(17)')
repl_eval('sim.modular.submod_2.rules.RL_inner_forward_2.get_can_fire()')
repl_exec('while not sim.modular.submod_2.rules.RL_inner_forward_2.get_can_fire():\n    sim.step(1)')
repl_eval('sim.modular.submod_2.rules.RL_inner_forward_2.get_can_fire()')
repl_eval('sim.modular.submod_2.rules.RL_inner_forward_2()')
repl_eval('sim.modular.submod_2.rules.RL_inner_forward_2.get_can_fire()')

