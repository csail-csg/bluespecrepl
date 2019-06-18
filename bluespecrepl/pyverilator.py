#!/usr/bin/env python3

import ctypes
import os
import subprocess
import json
import jinja2
import re
import bluespecrepl.vcd as vcd

_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
_jinja2_env = jinja2.Environment(loader = jinja2.FileSystemLoader(_template_path))
_verilator_cpp_wrapper_template = _jinja2_env.get_template('pyverilator_wrapper_template.cpp')

class PyVerilator:
    """Python interface for verilator simulation.
    
    sim = PyVerilator.build('my_verilator_file.v')
    sim['a'] = 2
    sim['b'] = 3
    sim.eval()
    print('c = ' + sim['c'])
    """

    @classmethod
    def build(cls, top_verilog_file, verilog_path = [], build_dir = 'obj_dir', json_data = None, gen_only = False, **kwargs):
        """Generate and build the Verilator model and return the PyVerilator instance."""

        # get the module name from the verilog file name
        top_verilog_file_base = os.path.basename(top_verilog_file)
        verilog_module_name, extension = os.path.splitext(top_verilog_file_base)
        if extension != '.v':
            raise ValueError('PyVerilator.build() expects top_verilog_file to be a verilog file ending in .v')

        # parse verilog file to get the names of inputs and outputs
        # Same programming pattern as for verilator later.
        yosys_args=['yosys','-q','-p', "read_verilog %s; select x:* %%n; delete; select *; write_json"%top_verilog_file]
        yosys = subprocess.Popen(yosys_args, stdout=subprocess.PIPE, stderr= subprocess.PIPE)
        yosys_out, yosys_err = yosys.communicate()
        if yosys.returncode != 0:
            raise ValueError('Failed to retrieve IO ports using Yosys')
        io_json = json.loads(yosys_out)['modules'][verilog_module_name]['ports'].items()
        inputs = list({ k:len(v['bits']) for (k,v) in io_json if v['direction'] == 'input'}.items())
        outputs = list({k: len(v['bits']) for (k, v) in io_json if v['direction'] == 'output'}.items())
        # inputs = verilog.get_inputs()
        # outputs = verilog.get_outputs()

        # prepare the path for the C++ wrapper file
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        verilator_cpp_wrapper_path = os.path.join(build_dir, 'pyverilator_wrapper.cpp')

        # call verilator executable to generate the verilator C++ files
        verilog_path_args = []
        for verilog_dir in verilog_path:
            verilog_path_args += ['-y', verilog_dir]
        # tracing is required in order to see internal signals
        verilator_args = ['bash', 'verilator', '-Wno-fatal', '-Mdir', build_dir] + verilog_path_args + ['--CFLAGS', '-fPIC --std=c++11', '--trace', '--cc', top_verilog_file, '--exe', verilator_cpp_wrapper_path]
        subprocess.call(verilator_args)

        # get internal signals by parsing the generated verilator output
        internal_signals = []
        verilator_h_file = os.path.join(build_dir, 'V' + verilog_module_name + '.h')
        with open(verilator_h_file) as f:
            for line in f:
                result = re.search(r'(VL_SIG[^(]*)\(([^,]+),([0-9]+),([0-9]+)(?:,[0-9]+)?\);', line)
                if result:
                    signal_name = result.group(2)
                    if signal_name.startswith(verilog_module_name) and '[' not in signal_name and int(result.group(4)) == 0:
                        # this is an internal signal
                        signal_width = int(result.group(3)) - int(result.group(4)) + 1
                        internal_signals.append((signal_name, signal_width))

        # generate the C++ wrapper file
        verilator_cpp_wrapper_code = _verilator_cpp_wrapper_template.render({
            'top_module' : verilog_module_name,
            'inputs' : inputs,
            'outputs' : outputs,
            'internal_signals' : internal_signals,
            'json_data' : json.dumps(json.dumps( json_data ))
            })
        with open(verilator_cpp_wrapper_path, 'w') as f:
            f.write(verilator_cpp_wrapper_code)

        # if only generating verilator C++ files, stop here
        if gen_only:
            return None

        # call make to build the pyverilator shared object
        make_args = ['make', '-C', build_dir, '-f', 'V%s.mk' % verilog_module_name, 'CFLAGS=-fPIC -shared', 'LDFLAGS=-fPIC -shared']
        subprocess.call(make_args)

        so_file = os.path.join(build_dir, 'V' + verilog_module_name)

        return cls(so_file, **kwargs)

    def __init__(self, so_file, *, auto_eval = True):
        # initialize lib and model first so if __init__ fails, __del__ will
        # not fail.
        self.lib = None
        self.model = None
        self.so_file = so_file
        self.auto_eval = auto_eval
        # initialize vcd variables
        self.vcd_filename = None
        self.vcd_trace = None
        self.auto_tracing_mode = None
        self.curr_time = 0
        self.vcd_reader = None

        self.lib = ctypes.CDLL(so_file)
        construct = self.lib.construct
        construct.restype = ctypes.c_void_p
        self.model = construct()

        # get inputs, outputs, internal_signals, and json_data
        self._read_embedded_data()

        self._sim_init()

    def __del__(self):
        if self.model is not None:
            fn = self.lib.destruct
            fn.argtypes = [ctypes.c_void_p]
            fn(self.model)
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

        # internal signals
        num_internal_signals = ctypes.c_uint32.in_dll(self.lib, '_pyverilator_num_internal_signals').value
        internal_signal_names = (ctypes.c_char_p * num_internal_signals).in_dll(self.lib, '_pyverilator_internal_signals')
        internal_signal_widths = (ctypes.c_uint32 * num_internal_signals).in_dll(self.lib, '_pyverilator_internal_signal_widths')
        self.internal_signals = []
        for i in range(num_internal_signals):
            self.internal_signals.append((internal_signal_names[i].decode('ascii'), internal_signal_widths[i]))

        # json_data
        json_string = ctypes.c_char_p.in_dll(self.lib, '_pyverilator_json_data').value.decode('ascii')
        self.json_data = json.loads(json_string)

    def _read(self, port_name):
        port_width = None
        for name, width in self.inputs + self.outputs + self.internal_signals:
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
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_uint32
        return int(fn(self.model))

    def _read_64(self, port_name):
        fn = getattr(self.lib, 'get_' + port_name)
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_uint64
        return int(fn(self.model))

    def _read_words(self, port_name, num_words):
        fn = getattr(self.lib, 'get_' + port_name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
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
        if self.auto_tracing_mode == 'CLK' and port_name == 'CLK':
            self.add_to_vcd_trace()

    def _write_32(self, port_name, value):
        fn = getattr(self.lib, 'set_' + port_name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        fn( self.model, ctypes.c_uint32(value) )

    def _write_64(self, port_name, value):
        fn = getattr(self.lib, 'set_' + port_name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        fn( self.model, ctypes.c_uint64(value) )

    def _write_words(self, port_name, num_words, value):
        fn = getattr(self.lib, 'set_' + port_name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32]
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
        for name, _ in self.inputs + self.outputs + self.internal_signals:
            if name == signal_name:
                return True
        return False

    def eval(self):
        fn = self.lib.eval
        fn.argtypes = [ctypes.c_void_p]
        fn(self.model)
        if self.auto_tracing_mode == 'eval':
            self.add_to_vcd_trace()

    def start_vcd_trace(self, filename, auto_tracing = True):
        if self.vcd_trace is not None:
            raise ValueError('start_vcd_trace() called while VCD tracing is already active')
        start_vcd_trace = self.lib.start_vcd_trace
        start_vcd_trace.restype = ctypes.c_void_p
        self.vcd_trace = start_vcd_trace(self.model, ctypes.c_char_p(filename.encode('ascii')))
        self.vcd_filename = filename

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
        if self.vcd_trace is None:
            raise ValueError('add_to_vcd_trace() requires VCD tracing to be active')
        # do two steps so the most recent value in GTKWave is more obvious
        self.curr_time += 5
        self.lib.add_to_vcd_trace(self.vcd_trace, self.curr_time)
        self.curr_time += 5
        self.lib.add_to_vcd_trace(self.vcd_trace, self.curr_time)
        # go ahead and flush on each vcd update
        self.flush_vcd_trace()

    def flush_vcd_trace(self):
        if self.vcd_trace is None:
            raise ValueError('flush_vcd_trace() requires VCD tracing to be active')
        self.lib.flush_vcd_trace(self.vcd_trace)

    def stop_vcd_trace(self):
        if self.vcd_trace is None:
            raise ValueError('stop_vcd_trace() requires VCD tracing to be active')
        self.lib.stop_vcd_trace(self.vcd_trace)
        self.vcd_trace = None
        self.auto_tracing_mode = None
        self.vcd_filename = None

    def get_vcd_signal(self, signal_name):
        if self.vcd_trace is None:
            raise ValueError('get_vcd_signal() requires VCD tracing to be active')
        if self.vcd_reader is None:
            self.vcd_reader = vcd.VCD(self.vcd_filename)
        if self.vcd_reader.curr_time != self.curr_time:
            self.vcd_reader.reload()
        return self.vcd_reader.get_signal_value(signal_name)

    def get_vcd_signals(self):
        if self.vcd_trace is None:
            raise ValueError('get_vcd_signal() requires VCD tracing to be active')
        if self.vcd_reader is None:
            self.vcd_reader = vcd.VCD(self.vcd_filename)
        if self.vcd_reader.curr_time != self.curr_time:
            self.vcd_reader.reload()
        return self.vcd_reader.get_signals()
