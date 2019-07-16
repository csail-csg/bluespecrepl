import os
from bluespecrepl import bsvproject, bsvutil, pyverilatorbsv

# setup build directory and cd to it
build_dir = os.path.join(os.path.dirname(__file__), 'build', os.path.basename(__file__))
os.makedirs(build_dir, exist_ok = True)
os.chdir(build_dir)

# create the GCD bsv file
# use add_line_macro to get useful file and line numbers from the bluespec compiler in case of errors
bsv = bsvutil.add_line_macro('''
interface GCD;
    method Action start(Bit#(32) a, Bit#(32) b);
    method Bool result_ready();
    method Bit#(32) result();
    method Action result_deq();
endinterface

typedef enum {ReadyForInput, Busy, OutputReady} GCDState deriving (Bits, Eq, FShow);

(* synthesize *)
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

# create a BSVProject
proj = bsvproject.BSVProject('GCD.bsv', 'mkGCD')

# create a bspec project file for the bluespec GUI
# this project can be opened by running "bluespec gcd.bspec"
proj.export_bspec_project_file('gcd.bspec')

# build repl simulation executable with custom scheduling control
# this step does the following:
# 1) compiles the bluespec code to verilog using bsc
# 2) adds scheduling control to the module using verilogmutator.py and pyverilog
# 3) creates verilator c++ simulation code and compiles it using pyverilator
# 4) creates a python object (sim) with a bluespec-like interface to the verilator simulation
sim = proj.gen_python_repl(scheduling_control = True)

# set auto_eval, so if a signal is changed, run the eval() function
sim.auto_eval = True

# tells the verilator simulation to start dumping signal states to the given vcd file
sim.start_vcd_trace('gcd.vcd')

# now start the simulation

# wait until the start interface method is ready to call
while not sim.interface.start.is_ready():
    print('step until start.ready()')
    # this advances to the next clock cycle
    sim.step(1)

# call the start interface method
# since the start method is an action method, the method call also ticks the clock
print('start(105, 45)')
sim.interface.start(105, 45)

# advance to the next clock cycle until the result is ready
# this could also be done by calling sum.interface.result.is_ready()
while not sim.interface.result_ready():
    # display the current values of the x and y registers
    print('(x, y) = (%d, %d)' % (sim.internal.x.get_value(), sim.internal.y.get_value()))
    # advance to the next clock cycle
    sim.step(1)

# print the result
x = sim.interface.result()
print('result = ' + str(x))

# dequeue the result
print('result_deq()')
sim.interface.result_deq()

sim.step(1)

# viewing the VCD file

# start gtkwave, since we currently have vcd tracing enabled, gtkwave will open the existing trace
sim.start_gtkwave()
# send some signals and registers to gtkwave
sim.send_signal_to_gtkwave('CLK')
sim.send_reg_to_gtkwave('x')
sim.send_reg_to_gtkwave('y')
# state is an enumeration in bluespec
# when it is sent to gtkwave, it will display the enumeration value names
sim.send_reg_to_gtkwave('state')

# wait until the user presses enter
input('\nPress enter to quit...')

# close everything
sim.stop_gtkwave()
sim.stop_vcd_trace()
