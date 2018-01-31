#!/usr/bin/env python3

import bluetcl
import pyverilator

class BSVInterfaceMethod:
    def __init__(self, sim, *args, ready = None, enable = None, output = None):
        self.sim = sim
        self.args = args
        self.ready = ready
        self.enable = enable
        self.output = output

    def is_ready(self):
        if self.ready:
            return bool(self.sim[self.ready])
        else:
            return True

    def __call__(self, *call_args):
        if not self.is_ready():
            raise Exception('this interface method is not ready')
        if len(call_args) != len(self.args):
            raise Exception('wrong number of arguments')
        for i in range(len(self.args)):
            self.sim[self.args[i]] = call_args[i]
        if self.enable:
            self.sim[self.enable] = 1
        if self.output:
            return self.sim[self.output]

class PyVerilatorBSV(pyverilator.PyVerilator):
    """PyVerilator instance with BSV-specific features."""

    default_vcd_filename = 'gtkwave.vcd'

    def __init__(self, so_file, module_name = None, bsc_build_dir = None, **kwargs):
        super().__init__(so_file, **kwargs)
        self.module_name = module_name
        self.bsc_build_dir = bsc_build_dir
        self.gtkwave_active = False

    def start_gtkwave(self):
        if self.vcd_filename is None:
            self.start_vcd_trace(PyVerilatorBSV.default_vcd_filename)
        self.gtkwave_active = True
        self.bluetcl = bluetcl.BlueTCL()
        self.bluetcl.start()
        self.bluetcl.eval('''
            package require Waves
            package require Virtual
            Bluetcl::flags set -verilog -p %s:+
            Bluetcl::module load %s
            set v [Waves::start_replay_viewer -e %s -backend -verilog -viewer GtkWave -Command gtkwave -Options -W -StartTimeout 20 -nonbsv_hierarchy /TOP/%s -DumpFile %s]
            $v start''' % (self.bsc_build_dir, self.module_name, self.module_name, self.module_name, self.vcd_filename))

    def send_reg_to_gtkwave(self, reg_name):
        if not self.gtkwave_active:
            raise ValueError('send_reg_to_gtkwave() requires GTKWave to be started using start_gtkwave()')
        self.bluetcl.eval('$v send_instance [lindex [Virtual::inst filter %s] 0] QOUT' % reg_name)

    def send_signal_to_gtkwave(self, signal_name):
        if not self.gtkwave_active:
            raise ValueError('send_reg_to_gtkwave() requires GTKWave to be started using start_gtkwave()')
        self.bluetcl.eval('$v send_objects [Virtual::signal filter %s]' % signal_name)

    def stop_gtkwave(self):
        if not self.gtkwave_active:
            raise ValueError('send_reg_to_gtkwave() requires GTKWave to be started using start_gtkwave()')
        self.bluetcl.eval('$v close')
        self.bluetcl.stop()
        self.gtkwave_active = False
        if self.vcd_filename == PyVerilatorBSV.default_vcd_filename:
            self.stop_vcd_trace()

    def flush_vcd_trace(self):
        super().flush_vcd_trace()
        if self.gtkwave_active:
            self.bluetcl.eval('''$v reload_dump_file''')

    def stop_vcd_trace(self):
        if self.gtkwave_active:
            raise ValueError('stop_vcd_trace() requires GTKWave to be stopped using stop_gtkwave()')
        super().stop_vcd_trace()

