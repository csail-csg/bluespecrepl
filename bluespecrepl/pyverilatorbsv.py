#!/usr/bin/env python3

from collections import namedtuple
import random
import bluespecrepl.bluetcl as bluetcl
import bluespecrepl.pyverilator as pyverilator

class BSVInterfaceMethod:
    def __init__(self, sim, *args, ready = None, enable = None, output = None):
        if ready is None:
            raise ValueError('BSVInterfaceMethod requires ready signal')
        self.sim = sim
        self.args = args
        self.ready = ready
        self.enable = enable
        self.output = output
        self.__doc__ = 'Interface method %s.\n\n' % ready[4:]
        self.__doc__ += 'Arguments:\n'
        if args:
            for arg in args:
                self.__doc__ += '    %s\n' % arg
        else:
            self.__doc__ += '    (none)\n'
        if output:
            self.__doc__ += 'Output Signal:\n    %s\n' % output
        if ready:
            self.__doc__ += 'Ready Signal:\n    %s\n' % ready
        if enable:
            self.__doc__ += 'Enable Signal:\n    %s\n' % enable

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
        ret = None
        if self.output:
            ret = self.sim[self.output]
        return ret

class PyVerilatorBSV(pyverilator.PyVerilator):
    """PyVerilator instance with BSV-specific features."""

    default_vcd_filename = 'gtkwave.vcd'

    @classmethod
    def build(cls, top_verilog_file, verilog_path = [], build_dir = 'obj_dir', rules = [], gen_only = False, **kwargs):
        json_data = {'rules' : rules}
        return super().build(top_verilog_file, verilog_path, build_dir, json_data, gen_only, **kwargs)

    def __init__(self, so_file, module_name = None, bsc_build_dir = None, rules = [], **kwargs):
        super().__init__(so_file, **kwargs)
        self.rules = self.json_data['rules']
        self.module_name = module_name
        self.bsc_build_dir = bsc_build_dir
        self.gtkwave_active = False
        self._autodetect_interface_methods()

    def _autodetect_interface_methods(self):
        # look for ready outputs to get all the interface method names
        method_names = []
        for output_name, width in self.outputs:
            if output_name.startswith('RDY_'):
                method_names.append(output_name[4:])
        # now populate the signals of each interface method
        methods = {}
        for method_name in method_names:
            # initialize method signals
            method_inputs = []
            method_output = None
            enable_signal = None
            ready_signal = 'RDY_' + method_name
            for name, width in self.outputs:
                if name == method_name:
                    method_output = name
            for name, width in self.inputs:
                if name == ('EN_' + method_name):
                    enable_signal = name
                if name.startswith(method_name + '_'):
                    method_inputs.append(name)
            methods[method_name] = BSVInterfaceMethod(self, *method_inputs, ready = ready_signal, enable = enable_signal, output = method_output)
        # now fill in a named tuple containing all the interface methods
        # note: using a named tuple here adds some contraints to interface
        # method names
        Interface = namedtuple('Interface', method_names)
        self.interface = Interface(**methods)

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

    ### Repl functions
    def set_fire(self, rules_to_fire):
        """Sets the BLOCK_FIRE signal to one for every rule that is not in rules_to_fire."""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        new_block_fire = -1
        for rule in rules_to_fire:
            index = self.rules.index(rule)
            new_block_fire = new_block_fire & ~(1 << index)
        self['BLOCK_FIRE'] = new_block_fire

    def run_bsc_schedule(self, n, print_fired_rules = False):
        """Do n steps of the design with the scheduler created by the Bluespec compiler."""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        self['BLOCK_FIRE'] = 0
        for i in range(n):
            self.step(print_fired_rules)

    def list_can_fire(self):
        """List the rules with CAN_FIRE = 1"""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        can_fire_rules = []
        can_fire_bits = self['CAN_FIRE']
        for i in range(len(self.rules)):
            if ((can_fire_bits >> i) & 1) == 1:
                can_fire_rules.append(self.rules[i])
        return can_fire_rules

    def list_will_fire(self):
        """List the rules with WILL_FIRE = 1"""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        will_fire_rules = []
        will_fire_bits = self['WILL_FIRE']
        for i in range(len(self.rules)):
            if ((will_fire_bits >> i) & 1) == 1:
                will_fire_rules.append(self.rules[i])
        return will_fire_rules

    def run_random_schedule(self, n, print_fired_rules = False):
        """Do n steps of the design, where rules are picked to fire at random."""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        for i in range(n):
            chosen = random.choice(self.list_can_fire())
            self.set_fire([chosen])
            self.step(print_fired_rules)

    def run_until_predicate(self, predicate, print_fired_rules = False):
        """
        Run until the predicate is true

        example:
        a.run_until_predicate((lambda x: True if 'rule' in x.list_will_fire() else False))
        """
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        n = 0
        self.setfire(self.listrules)
        while not predicate(self):
            self.step(print_fired_rules)
            n += 1
        print("Predicate encountered after %d steps" % n)

    def step(self, n = 1, print_fired_rules = False):
        for i in range(n):
            self.eval()
            if (print_fired_rules):
                print(self.list_will_fire())
            self['CLK'] = 0
            self.eval()
            self['CLK'] = 1
            self.eval()

