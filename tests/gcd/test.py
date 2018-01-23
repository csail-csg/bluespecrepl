#!/usr/bin/env python3

import sys
sys.path.append("../../scripts")
import bsvproject
import tclwrapper

proj = bsvproject.BSVProject('GCD.bsv', 'mkGCD')
sim = proj.gen_python_repl(scheduling_control = True)
proj.export_bspec_project_file('gcd.bspec')
# set auto_eval, so if a signal is changed, run the eval() function
sim.auto_eval = True

# debug output
print('List of inputs:\n  ' + '\n  '.join([str(x) for x in sim.inputs]))
print('List of outputs:\n  ' + '\n  '.join([str(x) for x in sim.outputs]))
print('List of rules:\n  ' + '\n  '.join(sim.rules))

# code that belongs somewhere else (probably pyverilator or some class that
# extends it)
class BSVInterfaceMethod:
    def __init__(self, sim, *args, ready = None, enable = None, output = None):
        self.sim = sim
        self.args = args
        self.ready = ready
        self.enable = enable
        self.output = output

    def is_ready(self):
        if self.ready:
            return bool(sim[self.ready])
        else:
            return True

    def __call__(self, *call_args):
        if not self.is_ready():
            raise Exception('this interface method is not ready')
        if len(call_args) != len(self.args):
            raise Exception('wrong number of arguments')
        for i in range(len(self.args)):
            sim[self.args[i]] = call_args[i]
        if self.enable:
            sim[self.enable] = 1
        if self.output:
            return sim[self.output]

def tick(n, sim = sim):
    for i in range(n):
        sim['CLK'] = 0
        sim.eval()
        # TODO add vcd function
        sim['CLK'] = 1
        sim.eval()
        # TODO add vcd function
        # clear all method enables
        sim['EN_start'] = 0
        sim['EN_result_deq'] = 0

# module-specific code
start = BSVInterfaceMethod(sim, 'start_a', 'start_b', ready = 'RDY_start', enable = 'EN_start')
result_ready = BSVInterfaceMethod(sim, output = 'result_ready')
result_deq = BSVInterfaceMethod(sim, ready = 'RDY_result_deq', enable = 'EN_result_deq')
result = BSVInterfaceMethod(sim, output = 'result', ready = 'RDY_result')

sim.start_vcd_trace('gcd.vcd')

# test
while not start.is_ready():
    print('tick until start.ready()')
    tick(1)

print('start(105, 45)')
start(105, 45)

while not result_ready():
    print('tick until result_ready()')
    tick(1)

x = result()
print('result = ' + str(x))
tick(1)

print('result_deq()')
result_deq()

tick(1)

sim.stop_vcd_trace()

# load gtkwave

with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
    bluetcl.eval('''
        package require Virtual
        package require Waves

        Bluetcl::flags set "-verilog" -p %s:+
        Bluetcl::module load mkGCD

        set v [Waves::start_replay_viewer -e mkGCD -backend -verilog -viewer GtkWave -Command gtkwave -StartTimeout 5]
        $v start

        $v load_dump_file 'gcd.vcd'
        ''' % proj.build_dir)
    bluetcl.eval('''
        set will_fires [Virtual::signal filter *WILL_FIRE*]
        $v send_objects $will_fires
        ''')
    import time
    time.sleep(100)

