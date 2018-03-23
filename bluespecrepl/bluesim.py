#!/usr/bin/python3

import warnings
import bluespecrepl.bluetcl as bluetcl

def parse_bsv_hex_literal(value_string):
    split_value_string = value_string.split('h')
    if len(split_value_string) != 2:
        raise ValueError('Unexpected value format obtained: "%s"' % value_string)
    return int(split_value_string[-1], base=16)

class Bluesim:
    def __init__(self, so_file, top_module):
        self.so_file = so_file
        self.top_module = top_module
        self.vcd_trace_active = False
        self.bluetcl = bluetcl.BlueTCL()
        self.bluetcl.start()
        self.bluetcl.eval('package require Bluesim')
        self.bluetcl.eval('Bluesim::sim load %s %s' % (self.so_file, self.top_module))
        self.objects = {}
        self._populate_objects()

    def _populate_objects(self, hierarchy = []):
        object_handles = self.bluetcl.eval('Bluesim::sim lookup *', to_list = True)
        for h in object_handles:
            desc = self.bluetcl.eval('Bluesim::sim describe ' + h, to_list = True)
            object_name = desc[0]
            object_type = desc[1]
            full_name = '/'.join(hierarchy + [object_name])
            if object_type not in self.objects:
                self.objects[object_type] = {full_name : h}
            else:
                self.objects[object_type][full_name] = h
            if object_type in ['module', 'module with value']:
                self.bluetcl.eval('Bluesim::sim cd ' + object_name)
                self._populate_objects(hierarchy + [object_name])
                self.bluetcl.eval('Bluesim::sim up')

    def __del__(self):
        self.bluetcl.stop()

    def __getitem__(self, signal_name):
        return self._read(signal_name)

    def step(self, n = 1):
        self.bluetcl.eval('Bluesim::sim step ' + str(n))

    def start_vcd_trace(self, filename):
        if self.vcd_trace_active:
            raise ValueError('start_vcd_trace() called while VCD tracing is already active')
        self.bluetcl.eval('Bluesim::sim vcd ' + filename)
        self.bluetcl.eval('Bluesim::sim vcd on')
        self.vcd_trace_active = True

    def add_to_vcd_trace(self):
        pass

    def stop_vcd_trace(self):
        if not self.vcd_trace_active:
            raise ValueError('stop_vcd_trace() requires VCD tracing to be active')
        self.bluetcl.eval('Bluesim::sim vcd off')
        self.vcd_trace_active = False

    def get_internal_signal(self, signal_name, low_index = None, high_index = None):
        # unlike verilator, bluesim does not use VCD tracing for reading internal signals
        # check low_index and high_index:
        if high_index is not None and low_index is None:
            raise ValueError('high_index should not be defined without low_index')

        warnings.warn("Don't use this for non-registers")
        for obj_type in self.objects:
            if signal_name in self.objects[obj_type]:
                # check for 'module range(0:7)'
                if 'range' in obj_type:
                    min_val, max_val = tuple(obj_type.split('range')[1][1:-1].split(':'))
                    min_val = int(min_val)
                    max_val = int(max_val)
                    if high_index is None and low_index is None:
                        high_index = max_val
                        low_index = min_val
                    if high_index is None:
                        # just reading one value
                        value_string = self.bluetcl.eval('Bluesim::sim getrange %s %d' % (self.objects[obj_type][signal_name], low_index), to_list = False)
                        return parse_bsv_hex_literal(value_string)
                    else:
                        # reading a list of values
                        value_strings = self.bluetcl.eval('Bluesim::sim getrange %s %d %d' % (self.objects[obj_type][signal_name], low_index, high_index), to_list = True)
                        return list(map(parse_bsv_hex_literal, value_strings))
                else:
                    value_string = self.bluetcl.eval('Bluesim::sim get ' + self.objects[obj_type][signal_name])
                    return parse_bsv_hex_literal(value_string)
        raise ValueError('Unable to find signal "%s"' % signal_name)

