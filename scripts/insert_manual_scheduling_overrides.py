#!/usr/bin/env python3

import sys
import re
from has_bad_can_fires import *

def get_scheduling_signals(verilog_source):
    # scheduling_signal_definition_regex = re.compile(r'wire {WILL,CAN}_FIRE[ ,\w]*;')
    can_fire_assignment_regex = re.compile(r'assign CAN_FIRE_([$\w]*) =(.*?);', re.DOTALL)
    will_fire_assignment_regex = re.compile(r'assign WILL_FIRE_([$\w]*) =(.*?);', re.DOTALL)
    can_fire_assignments = can_fire_assignment_regex.findall(verilog_source)
    will_fire_assignments = will_fire_assignment_regex.findall(verilog_source)
    scheduling_signals = {}
    for name, value in can_fire_assignments:
        scheduling_signals[name] = {'CAN_FIRE': value}
    for name, value in will_fire_assignments:
        if name not in scheduling_signals:
            print('WARNING: WILL_FIRE signal for "%s" does not have corresponding CAN_FIRE signal' % name)
            scheduling_signals[name] = {'WILL_FIRE': value}
        else:
            scheduling_signals[name]['WILL_FIRE'] = value
    for name in scheduling_signals:
        value = scheduling_signals[name]
        if 'WILL_FIRE' not in value:
            print('WARNING: CAN_FIRE signal for "%s" does not have corresponding WILL_FIRE signal' % name)
    return scheduling_signals

def filter_scheduling_signals(scheduling_signals):
    keep_scheduling_signals = {}
    for name in scheduling_signals:
        # only keep scheduling signals that start with RL_
        if name.startswith('RL_'):
            keep_scheduling_signals[name] = scheduling_signals[name]
    return keep_scheduling_signals

def add_internal_scheduling_overrides_to_verilog(scheduling_signals, verilog_source):
    # generate new declarations for FORCE_WILL_FIRE_* and BLOCK_WILL_FIRE_*
    new_declarations = []
    for name in scheduling_signals:
        new_declarations.append('reg FORCE_WILL_FIRE_%s /* verilator public */;' % name)
        new_declarations.append('reg BLOCK_WILL_FIRE_%s /* verilator public */;' % name)
        new_declarations.append('initial FORCE_WILL_FIRE_%s = 0;' % name)
        new_declarations.append('initial BLOCK_WILL_FIRE_%s = 0;' % name)

    # insert new declarations with other declarations
    declaration_start = '// rule scheduling signals'
    before, match, after = verilog_source.partition(declaration_start)
    verilog_source = before + match + ('\n  ' + ('\n  '.join(new_declarations))) + after

    # update WILL_FIRE_* definitions to include FORCE_WILL_FIRE_* and BLOCK_WILL_FIRE_*
    for name in scheduling_signals:
        will_fire = scheduling_signals[name]['WILL_FIRE']
        # new WILL_FIRE_* definition, includes FORCE_WILL_FIRE and BLOCK_WILL_FIRE
        new_will_fire = 'FORCE_WILL_FIRE_%s | ((~BLOCK_WILL_FIRE_%s) & (%s))' % (name, name, will_fire)
        # now update the WILL_FIRE_* definition in the source
        verilog_source = re.sub(r'assign WILL_FIRE_%s =.*?;' % name,
                            'assign WILL_FIRE_%s = %s;' % (name, new_will_fire),
                            verilog_source,
                            count = 1,
                            flags = re.DOTALL)
    return verilog_source

def generate_c_wrapper(module_name, scheduling_signals):
    c_wrapper = ''
    c_wrapper += '#include <cstddef>\n'
    c_wrapper += '#include "verilated.h"\n'
    c_wrapper += '#include "V%s.h"\n' % module_name
    c_wrapper += '#include "V%s_%s.h"\n' % (module_name, module_name)
    c_wrapper += '\n'
    c_wrapper += 'V%s* top = std::nullptr;\n\n' % module_name
    c_wrapper += 'extern "C"\n'
    c_wrapper += 'int construct() {\n'
    c_wrapper += '    Verilated::commandArgs(0, NULL);\n'
    c_wrapper += '    if (top != std::nullptr) {\n'
    c_wrapper += '        delete top;\n'
    c_wrapper += '    }\n'
    c_wrapper += '    top = new V%s();\n'
    c_wrapper += '}\n'
    c_wrapper += 'extern "C"\n'
    c_wrapper += 'int destruct() {\n'
    c_wrapper += '    if (top != std::nullptr) {\n'
    c_wrapper += '        delete top;\n'
    c_wrapper += '        top = std::nullptr;\n'
    c_wrapper += '    }\n'
    c_wrapper += '    return 0;\n'
    c_wrapper += '}\n'
    c_wrapper += '\n'
    for name in scheduling_signals:
        signals = ['CAN_FIRE_' + name, 'FORCE_WILL_FIRE_' + name, 'BLOCK_WILL_FIRE_' + name]
        for signal in signals:
            c_wrapper += 'extern "C"\n'
            c_wrapper += 'int get_%s() {\n' % signal
            c_wrapper += '    return top->%s->%s;\n' % (module_name, signal)
            c_wrapper += '}\n'
            if not signal.startswith('CAN_FIRE'):
                c_wrapper += 'extern "C"\n'
                c_wrapper += 'int set_%s(int x) {\n' % signal
                c_wrapper += '    top->%s->%s = x;\n' % (module_name, signal)
                c_wrapper += '    return 0;\n'
                c_wrapper += '}\n'
    return c_wrapper

def expose_scheduling_wires(verilog_filename):
    if verilog_filename[-2:] != '.v':
        print('ERROR: this function expects the verilog file to end with the extension .v')
        return
    verilog_source = ''
    with open(verilog_filename, 'r') as f:
        verilog_source = f.read()
    # first fix the usage of CAN_FIRE versus WILL_FIRE
    if has_bad_can_fires(verilog_source):
        print('ERROR: The verilog file %s uses CAN_FIRE in an unexpected context.' % verilog_filename)
        print('    This is probably a result of common sub-expression elimination in the compiler.')
        print('    Use the compiler flag -no-opt-ATS to avoid this issue.')
    # get the scheduling signals used in the design
    scheduling_signals = get_scheduling_signals(verilog_source)
    # only keep the scheduling signals that start with RL_
    scheduling_signals = filter_scheduling_signals(scheduling_signals)
    # add the internal scheduling overrides
    modified_verilog_source = add_internal_scheduling_overrides_to_verilog(scheduling_signals, verilog_source)
    # now generate the c file
    module_name_match = re.search(r'module ([$\w_]*)', modified_verilog_source)
    if not module_name_match:
        print('ERROR: Cannot find module name from searching modified verilog')
        return
    module_name = module_name_match.group(1)
    c_wrapper = generate_c_wrapper(module_name, scheduling_signals)
    # output to files
    with open(verilog_filename[:-2] + '_sched_override.v', 'w') as f:
        f.write(modified_verilog_source)
    with open(verilog_filename[:-2] + '_rules.txt', 'w') as f:
        f.write('\n'.join(scheduling_signals.keys()))
    with open(verilog_filename[:-2] + '_wrapper.cpp', 'w') as f:
        f.write(c_wrapper)

def main():
    if len(sys.argv) == 1:
        print('ERROR: this program expects a bluespec-generated verilog file (with -keep-fires) as a command-line argument')
    else:
        expose_scheduling_wires(sys.argv[1])

if __name__ == '__main__':
    main()
