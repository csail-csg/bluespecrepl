import random
import pyverilator
import bluespecrepl.bluetcl as bluetcl

def mynamedtuple(name, item_names):
    class mynamedtuple_internal:
        _item_names = item_names
        _item_dict = {}
        def __init__(self, item_dict):
            for item in item_dict:
                self._item_dict[item] = item_dict[item]
        def __setattr__(self, *args):
            raise BaseException('setting items not allowed')
        def __getattr__(self, arg):
            return self._item_dict[arg]
        def __getitem__(self, index):
            return self._item_dict[self._item_names[index]]
        def __repr__(self):
            ret = ''
            for item_name in self._item_names:
                ret += item_name + ': ' + repr(self._item_dict[item_name])
            return ret
        def __iter__(self):
            for item in self._item_names:
                yield self._item_dict[item]
        def __len__(self):
            return len(self._item_names)
    return mynamedtuple_internal

class BSVInterfaceMethod:
    def __init__(self, sim, *args, ready = None, enable = None, output = None):
        if ready is None or not ready.startswith('RDY_'):
            raise ValueError('BSVInterfaceMethod requires a ready signal that starts with RDY_')
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
        if self.enable:
            self.sim.step(1)
            self.sim[self.enable] = 0
        return ret

    def __str__(self):
        method_name = self.ready[4:] # drop RDY_
        arg_names = [arg[len(method_name)+1:] for arg in self.args]
        return method_name + '(' + ', '.join(arg_names) + ')'

    def __repr__(self):
        method_name = self.ready[4:] # drop RDY_
        arg_names = [arg[len(method_name)+1:] for arg in self.args]
        return '<' + str(self) + ('' if self.is_ready() else ' NOT_READY') + '>'

class BSVRule:
    def __init__(self, sim, name, index):
        self.sim = sim
        self.name = name
        self.index = index
        self.__doc__ = 'Rule %s.\n' % self.name

    def _get_index_of(self, port_name):
        return (self.sim[port_name] >> self.index) & 1

    def _set_index_of(self, port_name, value):
        if value == 0:
            self.sim[port_name] &= ~(1 << self.index)
        elif value == 1:
            self.sim[port_name] |= 1 << self.index
        else:
            raise ValueError('value should be a 0 or a 1')

    def get_can_fire(self):
        return bool(self._get_index_of('CAN_FIRE'))

    def get_will_fire(self):
        return bool(self._get_index_of('WILL_FIRE'))

    def get_force_fire(self):
        if 'FORCE_FIRE' in self.sim:
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

        old_block_fire = self.sim['BLOCK_FIRE']
        if 'FORCE_FIRE' in self.sim:
            old_force_fire = self.sim['FORCE_FIRE']

        self.sim['BLOCK_FIRE'] = ~(1 << self.index)
        if 'FORCE_FIRE' in self.sim:
            self.sim['FORCE_FIRE'] = 0

        if not self.get_can_fire():
            self.sim['BLOCK_FIRE'] = old_block_fire
            if 'FORCE_FIRE' in self.sim:
                self.sim['FORCE_FIRE'] = old_force_fire
            raise Exception('The guard for this rule is not true if all other rules are blocked. This can happen if this rule depends on another rule firing in the same cycle.')
        if not self.get_will_fire():
            self.sim['BLOCK_FIRE'] = old_block_fire
            if 'FORCE_FIRE' in self.sim:
                self.sim['FORCE_FIRE'] = old_force_fire
            raise Exception('This rule is blocked even though all other rules are blocked. This should not be possible.')

        self.sim.step(1)

        self.sim['BLOCK_FIRE'] = old_block_fire
        if 'FORCE_FIRE' in self.sim:
            self.sim['FORCE_FIRE'] = old_force_fire

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

class PyVerilatorBSV(pyverilator.PyVerilator):
    """PyVerilator instance with BSV-specific features."""

    default_vcd_filename = 'gtkwave.vcd'

    @classmethod
    def build(cls, top_verilog_file, verilog_path = [], build_dir = 'obj_dir', rules = [], gen_only = False, bsc_build_dir = 'build_dir'):
        json_data = {'rules' : rules, 'bsc_build_dir' : bsc_build_dir}
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
        self._populate_rules()
        self._populate_internal()
        self._populate_submodules()
        # reset the design
        if 'CLK' in self and 'RST_N' in self:
            self['RST_N'] = 0
            self['CLK'] = 0
            self['CLK'] = 1
            self['CLK'] = 0
            self['CLK'] = 1
            self['RST_N'] = 1

    def _populate_interface(self):
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
        class Interface(mynamedtuple('Interface', method_names)):
            def __repr__(self):
                ret = 'interface:'
                for i in self:
                    ret += '\n    ' + str(i)
                    if not i.is_ready():
                        ret += '    NOT_READY'
                return ret
        self.interface = Interface(methods)

    def _populate_rules(self):
        self.rules = self._get_rules()

    def _get_rules(self, submodule = None):
        rule_dict = {}
        rule_names = []
        for i in range(len(self.rule_names)):
            if submodule is not None:
                rule_submodule = self.rule_names[i].split('__DOT__')[:-1]
                if rule_submodule != submodule:
                    continue
                rule_short_name = self.rule_names[i].split('__DOT__')[-1]
                rule_dict[rule_short_name] = BSVRule(self, rule_short_name, i)
                rule_names.append(rule_short_name)
            else:
                rule_dict[self.rule_names[i]] = BSVRule(self, self.rule_names[i], i)
                rule_names.append(self.rule_names[i])
        class Rules(mynamedtuple('Rules', rule_names)):
            def __repr__(self):
                ret = 'rules:'
                for i in self:
                    ret += '\n    ' + str(i)
                    if i.get_force_fire():
                        ret += '    FORCE_FIRE'
                        if not i.get_can_fire():
                            ret += ' (CAN_FIRE is false)'
                    elif i.get_block_fire():
                        ret += '    BLOCK_FIRE'
                        if i.get_can_fire():
                            ret += ' (CAN_FIRE is true)'
                    elif i.get_will_fire():
                        ret += '    WILL_FIRE'
                    elif i.get_can_fire():
                        ret += '    CAN_FIRE (WILL_FIRE is false)'
                    else:
                        ret += '    (CAN_FIRE is false)'
                return ret
        return Rules(rule_dict)

    def _populate_internal(self):
        self.internal = self._get_internal()

    def _get_internal(self, submodule = None):
        signal_names = []
        signal_dict = {}
        for signal_name, signal_width in self.internal_signals:
            # '__024' is from having a $ is the signal name
            if 'CAN_FIRE_' in signal_name or 'WILL_FIRE_' in signal_name or '__024' in signal_name:
                continue
            # __DOT__ is used by verilator and bluespecrepl to denote module boundaries
            split_name = signal_name.split('__DOT__')
            # signal name without the top module's name
            short_name = signal_name.split('__DOT__', 1)[1]
            final_name = split_name[-1]
            signal_submodule = split_name[1:-1]
            if short_name.startswith('_') or final_name.startswith('_'):
                continue
            if submodule is not None:
                if signal_submodule != submodule:
                    continue
                signal_names.append(final_name)
                signal_dict[final_name] = BSVSignal(self, final_name, signal_name, signal_width)
            else:
                signal_names.append(short_name)
                signal_dict[short_name] = BSVSignal(self, short_name, signal_name, signal_width)
        signal_names.sort()
        class Internal(mynamedtuple('Internal', signal_names)):
            def __repr__(self):
                ret = 'internal:'
                for i in self:
                    ret += '\n    ' + str(i) + ' = ' + hex(i.get_value())
                return ret
        return Internal(signal_dict)

    def _get_submodules(self):
        # first use internal_signals, then use rules
        # this will (probably) return [] as one of the submodules representing to top level
        submodules = []
        for signal_name, signal_width in self.internal_signals:
            if 'CAN_FIRE_' in signal_name or 'WILL_FIRE_' in signal_name or '__024' in signal_name:
                continue
            submodule_name = signal_name.split('__DOT__')[1:-1]
            if submodule_name not in submodules:
                submodules.append(submodule_name)
        for rule_name in self.rule_names:
            submodule_name = rule_name.split('__DOT__')[:-1]
            if submodule_name not in submodules:
                submodules.append(submodule_name)
        submodules.sort()
        return submodules

    def _populate_submodules(self):
        submodules = self._get_submodules()
        submodules_by_depth = {}
        max_depth = 0
        for submodule in submodules:
            depth = len(submodule)
            if depth > max_depth:
                max_depth = depth
            if depth not in submodules_by_depth:
                submodules_by_depth[depth] = [submodule]
            else:
                submodules_by_depth[depth].append(submodule)
        # get rules and internals for each submodule
        populated_submodules = {}
        for d in range(max_depth, -1, -1):
            for submodule in submodules_by_depth.get(d, []):
                rules = self._get_rules(submodule)
                internals = self._get_internal(submodule)
                submodule_dot_name = '.'.join(submodule)
                child_depth = len(submodule) + 1
                child_submodule_names = [x for x in submodules_by_depth.get(child_depth, []) if x[:len(submodule)] == submodule]
                child_submodules = { x[-1] : populated_submodules['.'.join(x)] for x in child_submodule_names }
                child_submodule_short_names = list(child_submodules.keys())
                child_submodule_short_names.sort()
                class Submodule(mynamedtuple(submodule_dot_name, ['full_name', *child_submodule_short_names, 'rules', 'internals'])):
                    def __repr__(self):
                        ret = 'current module: ' + self[0]
                        ret += '\nsubmodules:'
                        for i in range(1, len(self) - 2):
                            ret += '\n    ' + self[i][0].split('.')[-1]
                        ret += '\n' + repr(self.rules)
                        ret += '\n' + repr(self.internals)
                        return ret
                submodule_dict = child_submodules.copy()
                if submodule_dot_name == '':
                    submodule_dict['full_name'] = '(TOP)'
                else:
                    submodule_dict['full_name'] = submodule_dot_name
                submodule_dict['rules'] = rules
                submodule_dict['internals'] = internals
                populated_submodules[submodule_dot_name] = Submodule(submodule_dict)
        if '' in populated_submodules:
            # only populate the submodules if at least one submodule was found
            self.modular = populated_submodules['']

    def __repr__(self):
        return repr(self.interface) + '\n' + repr(self.rules) + '\n' + repr(self.internal)

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
        """Flush the vcd trace to disc.

        If a gtkwave window is open, this also updates the window. If the window previously showed
        the most recent data, then the window is scrolled as necessary to show the newest data."""
        super().flush_vcd_trace()
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

