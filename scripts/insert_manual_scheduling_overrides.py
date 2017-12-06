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
        new_declarations.append('reg FORCE_WILL_FIRE_%s = 0 /* verilator public */;' % name)
        new_declarations.append('reg BLOCK_WILL_FIRE_%s = 0 /* verilator public */;' % name)

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

    with open(verilog_filename[:-2] + '_sched_override.v', 'w') as f:
        f.write(modified_verilog_source)
    with open(verilog_filename[:-2] + '_rules.txt', 'w') as f:
        f.write('\n'.join(scheduling_signals.keys()))

def main():
    if len(sys.argv) == 1:
        print('ERROR: this program expects a bluespec-generated verilog file (with -keep-fires) as a command-line argument')
    else:
        expose_scheduling_wires(sys.argv[1])

if __name__ == '__main__':
    main()
