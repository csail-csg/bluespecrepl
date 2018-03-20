#!/usr/bin/env python3

import random
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

    def step(self, print_fired_rules = False):
        self.eval()
        if (print_fired_rules):
            print(self.list_will_fire())
        self['CLK'] = 0
        self.eval()
        self['CLK'] = 1
        self.eval()

