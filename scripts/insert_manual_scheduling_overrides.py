#!/usr/bin/env python3

import sys
import os
import re
from has_bad_can_fires import *
import jinja2

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

def get_scheduling_order(verilog_source):
    # the 'assign CAN_FIRE_[$\w]*' appear in the output verilog file in scheduling order
    can_fire_assignments = re.findall('assign CAN_FIRE_([$\w]*)', verilog_source)
    return can_fire_assignments

def add_external_scheduling_overrides_to_verilog(rules, verilog_source):
    new_outputs = ['CAN_FIRE', 'WILL_FIRE']
    new_inputs = ['BLOCK_FIRE', 'FORCE_FIRE']
    new_ports = new_outputs + new_inputs
    new_port_width = len(rules)

    # generate new declarations for FORCE_WILL_FIRE_* and BLOCK_WILL_FIRE_* and update declarations for CAN_FIRE_*
    module_declaration_match = re.search(r'(module .*?\(.*?)(\);)', verilog_source, re.DOTALL)
    before = verilog_source[0:module_declaration_match.start()] + module_declaration_match.group(1)
    after = module_declaration_match.group(2) + verilog_source[module_declaration_match.end():]
    # add new ports to the end of the list of ports
    verilog_source = before + ',' + (','.join(new_ports)) + after
    # add definitions of the new ports
    port_declaration_matches = list(re.finditer(r'(input|output) .*?;', verilog_source, re.DOTALL))
    before = verilog_source[0:port_declaration_matches[-1].end()]
    after = verilog_source[port_declaration_matches[-1].end():]
    new_port_declarations = ''
    for new_output in new_outputs:
        new_port_declarations += '\n  output [%d:0] %s;' % (new_port_width - 1, new_output)
    for new_input in new_inputs:
        new_port_declarations += '\n  input [%d:0] %s;' % (new_port_width - 1, new_input)
    verilog_source = before + new_port_declarations + after

    # declare new internal signals
    new_declarations = []
    for new_input in new_inputs:
        for rule_name in rules:
            new_declarations.append('wire %s_%s;' % (new_input, rule_name))
    for new_output in new_outputs:
        new_declarations.append('wire [%d:0] %s;' % (new_port_width - 1, (new_output)))

    # add it before the other scheduling signal declarations
    match = re.search(r'wire (CAN|WILL)_FIRE', verilog_source)
    if match is None:
        print(verilog_source)
        print('ERROR: Unable to find "wire (CAN|WILL)_FIRE"')
    before = verilog_source[0:match.start()]
    after = verilog_source[match.start():]
    verilog_source = before + '\n  '.join(new_declarations) + '\n  ' + after

    # connect to their internal sigals
    new_assignments = []
    for new_input in new_inputs:
        i = 0
        for rule_name in rules:
            new_assignments.append('assign %s_%s = %s[%d];' % (new_input, rule_name, new_input, i))
            i += 1
    for new_output in new_outputs:
        signals_to_concat = list(map(lambda x: new_output + '_' + x, rules))
        signals_to_concat.reverse()
        new_assignments.append('assign %s = {%s};' % (new_output, ', '.join(signals_to_concat)))

    # add it before the other scheduling signal assignments
    match = re.search(r'assign (CAN|WILL)_FIRE', verilog_source)
    before = verilog_source[0:match.start()]
    after = verilog_source[match.start():]
    verilog_source = before + '\n  '.join(new_assignments) + '\n  ' + after

    # update WILL_FIRE_* definitions to include FORCE_FIRE_* and BLOCK_FIRE_*
    for rule_name in rules:
        verilog_source = re.sub(r'assign WILL_FIRE_%s =(.*?);' % rule_name,
                                r'assign WILL_FIRE_%s = FORCE_FIRE_%s | ((~BLOCK_FIRE_%s) & (\1));' % (rule_name, rule_name, rule_name),
                                verilog_source,
                                flags = re.DOTALL)
    return verilog_source

def expose_scheduling_wires(verilog_filename):
    if verilog_filename[-2:] != '.v':
        print('ERROR: this function expects the verilog file to end with the extension .v')
        return
    verilog_source = ''
    with open(verilog_filename, 'r') as f:
        verilog_source = f.read()
    # make sure CAN_FIRE isn't used in a context where it shouldn't be
    if has_bad_can_fires(verilog_source):
        print('ERROR: The verilog file %s uses CAN_FIRE in an unexpected context.' % verilog_filename)
        print('    This is probably a result of common sub-expression elimination in the compiler.')
        print('    Use the compiler flag -no-opt-ATS to avoid this issue.')
    # get the scheduling signals used in the design
    scheduling_signals = get_scheduling_signals(verilog_source)
    # only keep the scheduling signals that start with RL_
    scheduling_signals = filter_scheduling_signals(scheduling_signals)
    # get the scheduling order
    scheduling_order = get_scheduling_order(verilog_source)
    scheduling_signals_in_order = list(filter(lambda x: x in scheduling_signals, scheduling_order))

    # add the external scheduling overrides
    modified_verilog_source = add_external_scheduling_overrides_to_verilog(scheduling_signals_in_order, verilog_source)
    # now generate the c file
    module_name_match = re.search(r'module ([$\w_]*)', modified_verilog_source)
    if not module_name_match:
        print('ERROR: Cannot find module name from searching modified verilog')
        return
    module_name = module_name_match.group(1)

    template_path = os.path.dirname(os.path.realpath(__file__)) + '/templates/'
    #template_path = os.path.dirname(sys.argv[0]) + '/templates/'
    env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_path))
    template = env.get_template('verilator_cpp_wrapper.cpp')
    c_wrapper = template.render({
        'filename' : module_name,
        'rules' : scheduling_signals_in_order,
        'readable_signals' : ['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'],
        'writable_signals' : ['BLOCK_FIRE', 'FORCE_FIRE']
        })

    # output to files
    with open(verilog_filename[:-2] + '.v', 'w') as f:
        f.write(modified_verilog_source)
    with open(verilog_filename[:-2] + '_rules.txt', 'w') as f:
        f.write('\n'.join(scheduling_signals_in_order))
    with open(verilog_filename[:-2] + '_wrapper.cpp', 'w') as f:
        f.write(c_wrapper)

def main():
    if len(sys.argv) == 1:
        print('ERROR: this program expects a bluespec-generated verilog file (with -keep-fires) as a command-line argument')
    else:
        expose_scheduling_wires(sys.argv[1])

if __name__ == '__main__':
    main()
