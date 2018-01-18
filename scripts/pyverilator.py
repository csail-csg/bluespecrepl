#!/usr/bin/env python3

import ctypes
import os
import subprocess
import jinja2
import verilog_mutator

_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
_jinja2_env = jinja2.Environment(loader = jinja2.FileSystemLoader(_template_path))
_verilator_cpp_wrapper_template = _jinja2_env.get_template('pyverilator_wrapper_template.cpp')

class PyVerilator:
    """Python interface for verilator simulation.
    
    sim = PyVerilator.build('my_verilator_file.v')
    sim['a'] = 2
    sim['b'] = 3
    sim.eval()
    sim = PyVerilator(
    """

    @classmethod
    def build(cls, top_verilog_file, verilog_path = [], build_dir = 'obj_dir', rules = [], gen_only = False, auto_eval = True):
        # get the module name from the verilog file name
        top_verilog_file_base = os.path.basename(top_verilog_file)
        verilog_module_name, extension = os.path.splitext(top_verilog_file_base)
        if extension != '.v':
            raise ValueError('PyVerilator.build() expects top_verilog_file to be a verilog file ending in .v')

        # parse verilog file to get the names of inputs and outputs
        verilog = verilog_mutator.VerilogMutator(top_verilog_file)
        inputs = verilog.get_inputs()
        outputs = verilog.get_outputs()

        # generate the C++ wrapper file
        verilator_cpp_wrapper_code = _verilator_cpp_wrapper_template.render({
            'top_module' : verilog_module_name,
            'inputs' : inputs,
            'outputs' : outputs,
            'rules' : rules,
            })
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        verilator_cpp_wrapper_path = os.path.join(build_dir, 'pyverilator_wrapper.cpp')
        with open(verilator_cpp_wrapper_path, 'w') as f:
            f.write(verilator_cpp_wrapper_code)

        # call verilator executable to generate the verilator C++ files
        verilog_path_args = []
        for verilog_dir in verilog_path:
            verilog_path_args += ['-y', verilog_dir]
        verilator_args = ['bash', 'verilator', '-Wno-fatal', '-Mdir', build_dir] + verilog_path_args + ['--CFLAGS', '-fPIC --std=c++11', '--trace', '--cc', top_verilog_file, '--exe', verilator_cpp_wrapper_path]
        subprocess.call(verilator_args)

        # if only generating verilator C++ files, stop here
        if gen_only:
            return None

        # call make to build the pyverilator shared object
        make_args = ['make', '-C', build_dir, '-f', 'V%s.mk' % verilog_module_name, 'CFLAGS=-fPIC -shared', 'LDFLAGS=-fPIC -shared']
        subprocess.call(make_args)

        so_file = os.path.join(build_dir, 'V' + verilog_module_name)

        return PyVerilator(so_file, auto_eval)

    def __init__(self, so_file, auto_eval = True):
        # initialize lib and model first so if __init__ fails, __del__ will
        # not fail.
        self.lib = None
        self.model = None
        self.so_file = so_file
        self.auto_eval = auto_eval
        # initialize vcd variables
        self.vcd_trace = None
        self.auto_tracing_mode = None
        self.curr_time = 0

        self.lib = ctypes.CDLL(so_file)
        construct = self.lib.construct
        construct.restype = ctypes.c_void_p
        self.model = construct()

        # get inputs, outputs, and rules
        self._read_embedded_data()

        self._sim_init()

    def __del__(self):
        if self.model is not None:
            self.lib.destruct(self.model)
        if self.lib is not None:
            del self.lib

    def _read_embedded_data(self):
        # inputs
        num_inputs = ctypes.c_uint32.in_dll(self.lib, '_pyverilator_num_inputs').value
        input_names = (ctypes.c_char_p * num_inputs).in_dll(self.lib, '_pyverilator_inputs')
        input_widths = (ctypes.c_uint32 * num_inputs).in_dll(self.lib, '_pyverilator_input_widths')
        self.inputs = []
        for i in range(num_inputs):
            self.inputs.append((input_names[i].decode('ascii'), input_widths[i]))

        # outputs
        num_outputs = ctypes.c_uint32.in_dll(self.lib, '_pyverilator_num_outputs').value
        output_names = (ctypes.c_char_p * num_outputs).in_dll(self.lib, '_pyverilator_outputs')
        output_widths = (ctypes.c_uint32 * num_outputs).in_dll(self.lib, '_pyverilator_output_widths')
        self.outputs = []
        for i in range(num_outputs):
            self.outputs.append((output_names[i].decode('ascii'), output_widths[i]))

        # rules
        num_rules = ctypes.c_uint32.in_dll(self.lib, '_pyverilator_num_rules').value
        rule_names = (ctypes.c_char_p * num_rules).in_dll(self.lib, '_pyverilator_rules')
        self.rules = []
        for i in range(num_rules):
            self.rules.append(rule_names[i].decode('ascii'))

    def _read(self, port_name):
        port_width = None
        for name, width in self.inputs + self.outputs:
            if port_name == name:
                port_width = width
        if port_width is None:
            raise ValueError('cannot read port "%s" because it does not exist' % port_name)
        if port_width > 64:
            num_words = (port_width + 31) // 32
            return self._read_words(port_name, num_words)
        elif port_width > 32:
            return self._read_64(port_name)
        else:
            return self._read_32(port_name)

    def _read_32(self, port_name):
        fn = getattr(self.lib, 'get_' + port_name)
        fn.restype = ctypes.c_uint32
        return int(fn(self.model))

    def _read_64(self, port_name):
        fn = getattr(self.lib, 'get_' + port_name)
        fn.restype = ctypes.c_uint64
        return int(fn(self.model))

    def _read_words(self, port_name, num_words):
        fn = getattr(self.lib, 'get_' + port_name)
        fn.restype = ctypes.c_uint32
        words = [0] * num_words
        for i in range(num_words):
            words[i] = int(fn(self.model, i))
        out = 0
        for i in range(num_words):
            out |= words[i] << (i * 32)
        return out

    def _write(self, port_name, value):
        port_width = None
        for name, width in self.inputs:
            if port_name == name:
                port_width = width
        if port_width is None:
            raise ValueError('cannot write port "%s" because it does not exist (or it is an output)' % port_name)
        if port_width > 64:
            num_words = (port_width + 31) // 32
            self._write_words(port_name, num_words, value)
        elif port_width > 32:
            self._write_64(port_name, value)
        else:
            self._write_32(port_name, value)
        if self.auto_eval:
            self.eval()
        if self.auto_tracing_mode == 'CLK':
            self.add_to_vcd_trace()

    def _write_32(self, port_name, value):
        fn = getattr(self.lib, 'set_' + port_name)
        fn( self.model, ctypes.c_uint32(value) )

    def _write_64(self, port_name, value):
        fn = getattr(self.lib, 'set_' + port_name)
        fn( self.model, ctypes.c_uint64(value) )

    def _write_words(self, port_name, num_words, value):
        fn = getattr(self.lib, 'set_' + port_name)
        for i in range(num_words):
            word = ctypes.c_uint32(value >> (i * 32))
            fn( self.model, i, word )

    def _sim_init(self):
        # initialize all the inputs to 0
        input_names = [name for name, _ in self.inputs]
        for name in input_names:
            self._write(name, 0)
        # reset the design if there is a CLK and RST_N signal
        if 'RST_N' in input_names and 'CLK' in input_names:
            # reset the design
            for i in range(3):
                self['RST_N'] = 0
                self['CLK'] = 0
                self.eval()
                self['RST_N'] = 0
                self['CLK'] = 1
                self.eval()
            self['RST_N'] = 1
            self['CLK'] = 1
        self.eval()

    def __getitem__(self, signal_name):
        return self._read(signal_name)

    def __setitem__(self, signal_name, value):
        self._write(signal_name, value)

    def __contains__(self, signal_name):
        for name, _ in self.inputs + self.outputs:
            if name == signal_name:
                return True
        return False

    def eval(self):
        self.lib.eval(self.model)
        if self.auto_tracing_mode == 'eval':
            self.add_to_vcd_trace()

    def start_vcd_trace(self, filename, auto_tracing = True):
        start_vcd_trace = self.lib.start_vcd_trace
        start_vcd_trace.restype = ctypes.c_void_p
        self.vcd_trace = start_vcd_trace(self.model, ctypes.c_char_p(filename.encode('ascii')))

        if not auto_tracing:
            self.auto_tracing_mode = None
        elif 'CLK' in self:
            self.auto_tracing_mode = 'CLK'
        else:
            self.auto_tracing_mode = 'eval'
        self.curr_time = 0
        # initial vcd data
        self.add_to_vcd_trace()

    def add_to_vcd_trace(self):
        self.lib.add_to_vcd_trace(self.vcd_trace, self.curr_time)
        self.curr_time += 1

    def stop_vcd_trace(self):
        self.lib.stop_vcd_trace(self.vcd_trace)
        self.vcd_trace = None
        self.auto_tracing_mode = None

if __name__ == '__main__':
    test_verilog = '''
        module width_test (
                input_a,
                input_b,
                input_c,
                input_d,
                input_e,
                output_concat);
            input [7:0] input_a;
            input [15:0] input_b;
            input [31:0] input_c;
            input [63:0] input_d;
            input [127:0] input_e;
            output [247:0] output_concat;
            assign output_concat = {input_a, input_b, input_c, input_d, input_e};
        endmodule'''
    # make and move to test directory
    if not os.path.exists('test_pyverilator'):
        os.makedirs('test_pyverilator')
    os.chdir('test_pyverilator')
    # write test verilog file
    with open('width_test.v', 'w') as f:
        f.write(test_verilog)
    pyverilator = PyVerilator.build('width_test.v')

    pyverilator.start_vcd_trace('test.vcd')
    pyverilator['input_a'] = 0xaa
    pyverilator['input_b'] = 0x1bbb
    pyverilator['input_c'] = 0x3ccccccc
    pyverilator['input_d'] = 0x7ddddddddddddddd
    pyverilator['input_e'] = 0xfeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
    print('output_concat = ' + hex(pyverilator['output_concat']))
    pyverilator.stop_vcd_trace()
