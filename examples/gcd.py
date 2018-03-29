import os
from bluespecrepl import bsvproject, bsvutil, pyverilatorbsv

# setup build directory
build_dir = os.path.join('build',__file__)
os.makedirs(build_dir, exist_ok = True)
os.chdir(build_dir)

bsv = bsvutil.add_line_macro('''
interface GCD;
    method Action start(Bit#(32) a, Bit#(32) b);
    method Bool result_ready();
    method Bit#(32) result();
    method Action result_deq();
endinterface

typedef enum {ReadyForInput, Busy, OutputReady} GCDState deriving (Bits, Eq, FShow);

module mkGCD(GCD);
    Reg#(GCDState) state <- mkReg(ReadyForInput);
    Reg#(Bit#(32)) x <- mkReg(0);
    Reg#(Bit#(32)) y <- mkReg(0);

    rule swap((state == Busy) && (y > x) && (x != 0));
        x <= y;
        y <= x;
    endrule

    rule subtract((state == Busy) && (x >= y) && (x != 0));
        x <= x - y;
    endrule

    rule finish((state == Busy) && (x == 0));
        state <= OutputReady;
    endrule

    method Action start(Bit#(32) a, Bit#(32) b) if (state == ReadyForInput);
        x <= a;
        y <= b;
        state <= Busy;
    endmethod
    method Bool result_ready();
        return state == OutputReady;
    endmethod
    method Bit#(32) result() if (state == OutputReady);
        return y;
    endmethod
    method Action result_deq() if (state == OutputReady);
        state <= ReadyForInput;
    endmethod
endmodule
''')
with open('GCD.bsv', 'w') as f:
    f.write(bsv)

proj = bsvproject.BSVProject('GCD.bsv', 'mkGCD')
sim = proj.gen_python_repl(scheduling_control = True)
proj.export_bspec_project_file('gcd.bspec')
# set auto_eval, so if a signal is changed, run the eval() function
sim.auto_eval = True

sim.start_vcd_trace('gcd.vcd')

# test
while not sim.interface.start.is_ready():
    print('step until start.ready()')
    sim.step(1)

print('start(105, 45)')
sim.interface.start(105, 45)
sim.step(1)

while not sim.interface.result_ready():
    print('step until result_ready()')
    sim.step(1)

x = sim.interface.result()
print('result = ' + str(x))
sim.step(1)

print('result_deq()')
sim.interface.result_deq()

sim.step(1)

sim.stop_vcd_trace()
