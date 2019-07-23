import random
import pyverilator
import bluespecrepl.bluetcl as bluetcl
from tclwrapper import tclstring_to_nested_list

class BSVInterfaceMethod:
    def __init__(self, sim, name, args = [], ready = None, enable = None, output = None):
        self.sim = sim
        self.name = name
        # args is list of (bsv_name, signal, type)
        # bsv_name is not really the name used in the BSV source code
        self.args = args
        self.ready_signal = ready
        self.enable = enable
        # output is none or (signal, type)
        self.output = output

    def is_ready(self):
        if self.ready:
            return bool(self.ready_signal.value)
        else:
            return True

    @property
    def ready(self):
        return self.ready_signal.collection_get()

    def __call__(self, *call_args):
        if not self.is_ready():
            raise Exception('this interface method is not ready')
        if len(call_args) != len(self.args):
            raise Exception('wrong number of arguments')
        for i in range(len(self.args)):
            self.args[i][1].write(call_args[i])
        if self.enable:
            self.enable.write(1)
        ret = None
        if self.output:
            ret = self.output[0].value
        if self.enable:
            self.sim.step(1)
            self.enable.write(0)
        return ret

    def send_to_gtkwave(self):
        if self.ready is not None:
            self.sim.send_signal_to_gtkwave(self.ready)
        if self.enable is not None:
            self.sim.send_signal_to_gtkwave(self.enable)
        for _, sig, _ in self.args:
            self.sim.send_signal_to_gtkwave(sig)
        if self.output is not None:
            self.sim.send_signal_to_gtkwave(self.output[0])

    def bsv_decl(self):
        if self.output is None:
            output_type = 'Action'
        else:
            if self.enable is not None:
                output_type = 'ActionValue#(%s)' % self.output[1]
            else:
                output_type = self.output[1]
        args = [ arg_type + ' ' + bsv_name for bsv_name, _, arg_type in self.args ]
        decl = '{} {}({})'.format(output_type, self.name, ', '.join(args))
        return decl

    @property
    def status(self):
        return self.bsv_decl() + (' READY' if self.is_ready() else ' NOT_READY')

    def __str__(self):
        return self.bsv_decl()

    def __repr__(self):
        return self.bsv_decl() + (' READY' if self.is_ready() else ' NOT_READY')

class BSVRule:
    def __init__(self, sim, name, index, can_fire_signal = None, will_fire_signal = None):
        self.sim = sim
        self.name = name
        self.index = index
        self.can_fire_signal = can_fire_signal
        self.will_fire_signal = will_fire_signal
        self.__doc__ = 'Rule %s.\n' % self.name

    def _get_index_of(self, port_name):
        return (self.sim.io[port_name].value >> self.index) & 1

    def _set_index_of(self, port_name, value):
        if value == 0:
            self.sim.io[port_name].value &= ~(1 << self.index)
        elif value == 1:
            self.sim.io[port_name].value |= 1 << self.index
        else:
            raise ValueError('value should be a 0 or a 1')

    def get_can_fire(self):
        return bool(self._get_index_of('CAN_FIRE'))

    def get_will_fire(self):
        return bool(self._get_index_of('WILL_FIRE'))

    def get_force_fire(self):
        if 'FORCE_FIRE' in self.sim.io:
            return bool(self._get_index_of('FORCE_FIRE'))
        else:
            return False

    def get_block_fire(self):
        return bool(self._get_index_of('BLOCK_FIRE'))

    def set_force_fire(self, value):
        self._set_index_of('FORCE_FIRE', value)

    def set_block_fire(self, value):
        self._set_index_of('BLOCK_FIRE', value)

    def __call__(self, *call_args):
        if not self.get_can_fire():
            raise Exception('The guard for this rule is not true')

        old_block_fire = self.sim.io.BLOCK_FIRE.value
        if 'FORCE_FIRE' in self.sim.io:
            old_force_fire = self.sim.io.FORCE_FIRE.value

        self.sim.io.BLOCK_FIRE = ~(1 << self.index)
        if 'FORCE_FIRE' in self.sim.io:
            self.sim.io.FORCE_FIRE = 0

        if not self.get_can_fire():
            self.sim.io.BLOCK_FIRE = old_block_fire
            if 'FORCE_FIRE' in self.sim.io:
                self.sim.io.FORCE_FIRE = old_force_fire
            raise Exception('The guard for this rule is not true if all other rules are blocked. This can happen if this rule depends on another rule firing in the same cycle.')
        if not self.get_will_fire():
            self.sim.io.BLOCK_FIRE = old_block_fire
            if 'FORCE_FIRE' in self.sim.io:
                self.sim.io.FORCE_FIRE = old_force_fire
            raise Exception('This rule is blocked even though all other rules are blocked. This should not be possible.')

        self.sim.step(1)

        self.sim.io.BLOCK_FIRE = old_block_fire
        if 'FORCE_FIRE' in self.sim.io:
            self.sim.io.FORCE_FIRE = old_force_fire

    def send_to_gtkwave(self):
        if self.can_fire_signal is not None:
            self.sim.send_signal_to_gtkwave(self.can_fire_signal)
        if self.will_fire_signal is not None:
            self.sim.send_signal_to_gtkwave(self.will_fire_signal)

    @property
    def can_fire(self):
        if self.can_fire_signal is not None:
            return self.can_fire_signal.collection_get()
        else:
            return self.get_can_fire()

    @property
    def will_fire(self):
        if self.will_fire_signal is not None:
            return self.will_fire_signal.collection_get()
        else:
            return self.get_will_fire()

    @property
    def status(self):
        if not self.get_can_fire():
            return 'Not Ready'
        elif not self.get_will_fire():
            return 'Can Fire (Blocked)'
        else:
            return 'Will Fire'

    def __str__(self):
        return 'rule ' + self.name

    def __repr__(self):
        return '<' + str(self) + (' CAN_FIRE' if self.get_can_fire() else '') + (' WILL_FIRE' if self.get_will_fire() else '') + '>'

class BSVSignal:
    def __init__(self, sim, short_name, full_name, width):
        self.sim = sim
        self.short_name = short_name
        self.full_name = full_name
        self.width = width
        self.__doc__ = 'Signal %s (%d bits wide).\n' % (self.short_name, self.width)

    def get_value(self):
        return self.sim[self.full_name]

    def __str__(self):
        return 'signal ' + self.short_name

    def __repr__(self):
        return 'signal ' + self.short_name + ' = ' + hex(self.sim[self.full_name])

class Subinterface(pyverilator.Collection):
    pass

class PyVerilatorBSV(pyverilator.PyVerilator):
    """PyVerilator instance with BSV-specific features."""

    default_vcd_filename = 'gtkwave.vcd'

    @classmethod
    def build(cls, top_verilog_file, verilog_path = [], build_dir = 'obj_dir', interface = [], rules = [], gen_only = False, bsc_build_dir = 'build_dir'):
        json_data = {'interface' : interface, 'rules' : rules, 'bsc_build_dir' : bsc_build_dir}
        return super().build(top_verilog_file, verilog_path, build_dir, json_data, gen_only)

    def __init__(self, so_file, bsc_build_dir = None, **kwargs):
        super().__init__(so_file, **kwargs)
        self.rule_names = self.json_data['rules']
        if bsc_build_dir is not None:
            self.bsc_build_dir = bsc_build_dir
        else:
            self.bsc_build_dir = self.json_data['bsc_build_dir']
        self.gtkwave_active = False
        self._populate_interface()
        self._populate_signal_translation()
        self._populate_bsv_internals()
        self._populate_rules()
        self._populate_bsv_collection()
        # reset the design
        if 'CLK' in self and 'RST_N' in self:
            self['RST_N'] = 0
            self['CLK'] = 0
            self['CLK'] = 1
            self['CLK'] = 0
            self['CLK'] = 1
            self['RST_N'] = 1

    def _populate_interface(self):
        interface_json = self.json_data['interface']
        def get_signal(sig_name):
            if sig_name == '' or sig_name is None:
                return None
            else:
                return self.io[sig_name].signal
        # interface_json is a list of methods which are
        # dictionaries containing name, ready, enable, args, result
        methods = {}
        for hierarchy, interface in interface_json:
            name = interface['name']
            ready = get_signal(interface['ready'])
            enable = get_signal(interface['enable'])
            args = [(bsv_name, self.io[verilog_name].signal, type_name) for bsv_name, verilog_name, type_name in interface['args']]
            result = interface['result']
            if result is not None:
                verilog_name, type_name = result
                result = (self.io[verilog_name].signal, type_name)
            methods[tuple(hierarchy)] = BSVInterfaceMethod(self, name, args, ready, enable, result)
        self.interface = pyverilator.Collection.build_nested_collection(methods, nested_class = Subinterface)

    def _populate_rules(self):
        # self.rule_names has the names of all the rules in the order they
        # appear in CAN_FIRE, WILL_FIRE, BLOCK_FIRE, and if applicable,
        # FORCE_FIRE

        # To understand the different forms of rule names, consider the rule
        # "doStuff" that is in an unsynthesized "fifo" submodule that is
        # within a synthesized "submod" submodule of the top module.

        # In self.rule_names, this rule has the name "submod__DOT__RL_fifo_doStuff"

        # In the Virtual package in BlueTCL, rule names are split into names and
        # paths, and both names and paths have a bsv version and a synth version.
        # The above rule has the following names:
        #   path synth: "/submod"
        #   name synth: "RL_fifo_doStuff"
        #   path bsv: "/submod/fifo/doStuff"
        #   name bsv: "doStuff"

        # mapping from synth names to bsv names
        bsv_rule_translations = {}
        # bsv rule names (full path as tuple) in same order as self.rule_names
        bsv_rule_names = []

        with bluetcl.BlueTCL() as tcl:
            # [(bsv_name, bsv_path, synth_name, synth_path)]
            bluetcl_rule_names = tclstring_to_nested_list(tcl.eval('''
                package require Virtual
                Bluetcl::flags set -verilog -p %s:+
                Bluetcl::module load %s
                set rules [Virtual::inst filter -kind Rule *]
                set out {}
                foreach rule $rules {
                    set x {}
                    lappend x [$rule name bsv]
                    lappend x [$rule path bsv]
                    lappend x [$rule name synth]
                    lappend x [$rule path synth]
                    lappend out $x
                }
                return -level 0 $out
                ''' % (self.bsc_build_dir, self.module_name)))
            rule_signal_names = tclstring_to_nested_list(tcl.eval('''
                set signals [Virtual::signal filter *]
                set out {}
                foreach sig $signals {
                    if {[$sig kind] != "Signal"} {
                        set x {}
                        lappend x [$sig name]
                        lappend x [$sig path bsv]
                        lappend x [$sig path synth]
                        lappend out $x
                    }
                }
                return -level 0 $out
                '''))
        # if there is only zero or one rule, bluetcl_rule_names needs to be fixed up
        if isinstance(bluetcl_rule_names, str):
            if bluetcl_rule_names == '':
                bluetcl_rule_names = []
            else:
                bluetcl_rule_names = [bluetcl_rule_names.split()]
        # we can get all the bsv name information from bsv_path, so
        # we don't need to use bsv_name from bluetcl_rule_names
        for _, bsv_path, synth_name, synth_path in bluetcl_rule_names:
            # remove leading '/' and replace others with '__DOT__'
            verilog_name = synth_path[1:].replace('/', '__DOT__')
            if verilog_name != "":
                verilog_name += '__DOT__' + synth_name
            else:
                verilog_name = synth_name
            full_bsv_name = tuple(bsv_path[1:].split('/'))
            bsv_rule_translations[verilog_name] = full_bsv_name

        # get the bsv rule names in the same order as self.rule_names
        for verilog_rule_name in self.rule_names:
            bsv_rule_names.append( bsv_rule_translations[verilog_rule_name] )

        # look for WILL_FIRE/CAN_FIRE signals
        will_fire_signals = {}
        can_fire_signals = {}
        for synth_path, bsv_path in self.synth_to_bsv_path_translation.items():
            # use get on all_signals so if verilator optimized out a CAN_FIRE_*
            # or WILL_FIRE_* signal, the rule can still get the relevant info
            # from the 'CAN_FIRE' and 'WILL_FIRE' io signals.
            if bsv_path[-1].startswith('WILL_FIRE'):
                will_fire_signals[bsv_path[:-1]] = self.all_signals.get(synth_path)
            if bsv_path[-1].startswith('CAN_FIRE'):
                can_fire_signals[bsv_path[:-1]] = self.all_signals.get(synth_path)

        # construct a dict of rules that preserves the BSV module hierarchy
        self.all_rules = {}
        for i in range(len(bsv_rule_names)):
            bsv_rule_name = bsv_rule_names[i]
            self.all_rules[bsv_rule_name] = BSVRule(self, bsv_rule_name[-1], i, can_fire_signals[bsv_rule_name], will_fire_signals[bsv_rule_name])
        self.rules = pyverilator.Collection.build_nested_collection(self.all_rules, nested_class = pyverilator.Submodule)

    def _populate_signal_translation(self):
        """Constructs a dictionaries to translate signals and modular hierarchs to bsv names."""
        with bluetcl.BlueTCL() as tcl:
            tcl.eval('''
                package require Virtual
                Bluetcl::flags set -verilog -p %s:+
                Bluetcl::module load %s
                ''' % (self.bsc_build_dir, self.module_name))
            # [(bsv_name, bsv_path, synth_path)]
            # examples:
            #   (Q_OUT, /state/Q_OUT, /state/Q_OUT)
            #   (RDY_result, /RDY_result, /RDY_result)
            signal_names = tclstring_to_nested_list(tcl.eval('''
                set signals [Virtual::signal filter *]
                set out {}
                foreach sig $signals {
                    set x {}
                    lappend x [$sig name]
                    lappend x [$sig path bsv]
                    lappend x [$sig path synth]
                    lappend out $x
                }
                return -level 0 $out
                '''))
            # [(bsv_name, bsv_path)]
            prim_modules = tclstring_to_nested_list(tcl.eval('''
                set insts [Virtual::inst filter -kind Prim *]
                set out {}
                foreach inst $insts {
                    set x {}
                    lappend x [$inst name bsv]
                    lappend x [$inst path bsv]
                    lappend x [$inst name synth]
                    lappend x [$inst path synth]
                    lappend out $x
                }
                return -level 0 $out
            '''))
        # for bsv module hierarchy
        self.synth_to_bsv_path_translation = {}
        for _, bsv_path, synth_path in signal_names:
            # remove leading '/' and split at '/'
            real_synth_path = tuple(synth_path[1:].split('/'))
            real_bsv_path = tuple(bsv_path[1:].split('/'))
            self.synth_to_bsv_path_translation[real_synth_path] = real_bsv_path
        for _, bsv_path, _, synth_path in prim_modules:
            # remove leading '/' and split at '/'
            real_synth_path = tuple(synth_path[1:].split('/'))
            real_bsv_path = tuple(bsv_path[1:].split('/'))
            self.synth_to_bsv_path_translation[real_synth_path] = real_bsv_path
        # for sending signals to gtkwave
        # goal: /m_submodule/reg -> /m/submodule/reg/Q_OUT
        # goal: /m_submodule/reg$D_IN -> /m/submodule/reg/D_IN
        self.synth_to_bsv_signal_translation = {}
        for _, bsv_path, synth_path in signal_names:
            real_synth_path = tuple(synth_path[1:].split('/'))
            if real_synth_path[-1] == 'Q_OUT':
                real_synth_path = real_synth_path[:-1]
            if real_synth_path not in self.all_signals and len(real_synth_path) > 1:
                alt_synth_path = (*real_synth_path[:-2], real_synth_path[-2] + '$' + real_synth_path[-1])
                if alt_synth_path in self.all_signals:
                    real_synth_path = alt_synth_path
            if real_synth_path in self.all_signals:
                self.synth_to_bsv_signal_translation[real_synth_path] = bsv_path
        # check coverage
        # synth only signals are expected for imported Verilog
        synth_only_signals = []
        for synth_path in self.all_signals:
            if synth_path == ('CAN_FIRE',) or synth_path == ('WILL_FIRE',) or synth_path == ('BLOCK_FIRE',) or synth_path == ('FORCE_FIRE',):
                # these are expected to be synth-only paths
                continue
            if synth_path not in self.synth_to_bsv_signal_translation:
                synth_only_signals.append(synth_path)
        if len(synth_only_signals) != 0:
            print('Warning: %d signals were found in the Verilog that have no corresponding BSV signal name' % len(synth_only_signals))

    def _populate_bsv_internals(self):
        self.all_bsv_signals = {}
        for synth_signal_path, signal in self.all_signals.items():
            if synth_signal_path in self.synth_to_bsv_path_translation:
                self.all_bsv_signals[self.synth_to_bsv_path_translation[synth_signal_path]] = signal
        # remove IO and CanFire/WillFire signals (they will go in rules)
        internal_signals = { bsv_path: sig for bsv_path, sig in self.all_bsv_signals.items() if isinstance(sig, pyverilator.InternalSignal) and not bsv_path[-1].startswith('CAN_FIRE') and not bsv_path[-1].startswith('WILL_FIRE') }
        self.bsv_internals = pyverilator.Collection.build_nested_collection(internal_signals, nested_class = pyverilator.Submodule)

    def _populate_bsv_collection(self):
        self.all_bsv = { bsv_path: sig for bsv_path, sig in self.all_bsv_signals.items() if isinstance(sig, pyverilator.InternalSignal) and not bsv_path[-1].startswith('CAN_FIRE') and not bsv_path[-1].startswith('WILL_FIRE') }
        for k, v in self.all_rules.items():
            self.all_bsv[k] = v
        for method_name in self.interface:
            self.all_bsv[(method_name,)] = self.interface[method_name]
        self.bsv = pyverilator.Collection.build_nested_collection(self.all_bsv, nested_class = pyverilator.Submodule)

    def __repr__(self):
        return repr(self.interface) + '\n' + repr(self.rules)

    def start_gtkwave(self):
        if self.vcd_filename is None:
            self.start_vcd_trace(PyVerilatorBSV.default_vcd_filename)
        self.gtkwave_active = True
        self.bluetcl = bluetcl.BlueTCL('bluewish')
        self.bluetcl.start()
        self.bluetcl.eval('''
            wm withdraw .
            package require Waves
            package require Virtual
            package require GtkWaveSupport
            Bluetcl::flags set -verilog -p %s:+
            Bluetcl::module load %s
            set v [Waves::start_replay_viewer -e %s -backend -verilog -viewer GtkWave -Command gtkwave -Options -W -StartTimeout 20 -nonbsv_hierarchy /TOP/%s -DumpFile %s]
            $v start''' % (self.bsc_build_dir, self.module_name, self.module_name, self.module_name, self.vcd_filename))

    def send_signal_to_gtkwave(self, signal_name):
        """PyVerilator BSV-specific method for sending a Signal to GTKWave."""
        if not self.gtkwave_active:
            raise ValueError('send_reg_to_gtkwave() requires GTKWave to be started using start_gtkwave()')
        if isinstance(signal_name, pyverilator.Signal):
            bsv_name = self.synth_to_bsv_signal_translation[signal_name.modular_name]
            self.bluetcl.eval('$v send_objects [Virtual::signal filter {%s}]' % bsv_name)
        else:
            raise TypeError('PyVerilatorBSV.send_signal_to_gtkwave only supports pyverilator.Signals')

    def stop_gtkwave(self):
        if not self.gtkwave_active:
            raise ValueError('send_reg_to_gtkwave() requires GTKWave to be started using start_gtkwave()')
        self.bluetcl.eval('$v close')
        self.bluetcl.stop()
        self.gtkwave_active = False
        if self.vcd_filename == PyVerilatorBSV.default_vcd_filename:
            self.stop_vcd_trace()

    def reload_dump_file(self):
        if self.gtkwave_active:
            # this gets the max time before and after the dump file is reloaded to see if it changed
            old_max_time = float(self.bluetcl.eval('GtkWaveSupport::send_to_gtkwave "gtkwave::getMaxTime" value\nexpr $value'))
            self.bluetcl.eval('$v reload_dump_file')
            new_max_time = float(self.bluetcl.eval('GtkWaveSupport::send_to_gtkwave "gtkwave::getMaxTime" value\nexpr $value'))
            if new_max_time > old_max_time:
                # if it changed, see if the window could previously see the last data but not anymore
                window_end_time = float(self.bluetcl.eval('GtkWaveSupport::send_to_gtkwave "gtkwave::getWindowEndTime" value\nexpr $value'))
                if window_end_time >= old_max_time and window_end_time < new_max_time:
                    # if so, shift the window start so the new data is shown
                    time_shift_amt = new_max_time - window_end_time
                    window_start_time = float(self.bluetcl.eval('GtkWaveSupport::send_to_gtkwave "gtkwave::getWindowStartTime" value\nexpr $value'))
                    self.bluetcl.eval('GtkWaveSupport::send_to_gtkwave "gtkwave::setWindowStartTime %d" ignore' % (window_start_time + time_shift_amt))

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
            index = self.rule_names.index(rule)
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
        for i in range(len(self.rule_names)):
            if ((can_fire_bits >> i) & 1) == 1:
                can_fire_rules.append(self.rule_names[i])
        return can_fire_rules

    def list_will_fire(self):
        """List the rules with WILL_FIRE = 1"""
        if 'BLOCK_FIRE' not in self:
            raise ValueError('This function requires scheduling control in the Verilog')
        will_fire_rules = []
        will_fire_bits = self['WILL_FIRE']
        for i in range(len(self.rule_names)):
            if ((will_fire_bits >> i) & 1) == 1:
                will_fire_rules.append(self.rule_names[i])
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
        self.set_fire(self.rule_names)
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

