#!/usr/bin/env python3

import sys
try:
    from bluespecrepl import bsvproject
except Exception as e:
    print('ERROR: Unable to import bluespecrepl.bsvproject')
    raise e

proj = bsvproject.BSVProject('SimpleIntegration.bsv', 'mkSimpleIntegration')
sim = proj.gen_python_repl(scheduling_control = True)
# set auto_eval, so if a signal is changed, run the eval() function
sim.auto_eval = True

print('List of rules:  \n' + '\n  '.join(sim.rules))

def tick(n):
    for i in range(n):
        sim['CLK'] = 0
        sim['CLK'] = 1

tick(10)

def display_by_rule(signal, val):
    print(signal)
    for i in range(len(sim.rules)):
        print('    ' + signal + '_' + sim.rules[i] + ' = '+ str((val >> i) & 1))

display_by_rule('CAN_FIRE', sim['CAN_FIRE'])
display_by_rule('WILL_FIRE', sim['WILL_FIRE'])
display_by_rule('FORCE_FIRE', sim['FORCE_FIRE'])
display_by_rule('BLOCK_FIRE', sim['BLOCK_FIRE'])

print('\nblocking always_ready_and_enabled...\n')
sim['BLOCK_FIRE'] |= (1 << 3)

display_by_rule('CAN_FIRE', sim['CAN_FIRE'])
display_by_rule('WILL_FIRE', sim['WILL_FIRE'])
display_by_rule('FORCE_FIRE', sim['FORCE_FIRE'])
display_by_rule('BLOCK_FIRE', sim['BLOCK_FIRE'])

print('\nticking clock...\n')
tick(1)

display_by_rule('CAN_FIRE', sim['CAN_FIRE'])
display_by_rule('WILL_FIRE', sim['WILL_FIRE'])
display_by_rule('FORCE_FIRE', sim['FORCE_FIRE'])
display_by_rule('BLOCK_FIRE', sim['BLOCK_FIRE'])

print('\nblocking all rules...\n')
sim['BLOCK_FIRE'] = (1 << len(sim.rules)) - 1

display_by_rule('CAN_FIRE', sim['CAN_FIRE'])
display_by_rule('WILL_FIRE', sim['WILL_FIRE'])
display_by_rule('FORCE_FIRE', sim['FORCE_FIRE'])
display_by_rule('BLOCK_FIRE', sim['BLOCK_FIRE'])

print('\nticking clock 5 times...\n')
tick(5)

display_by_rule('CAN_FIRE', sim['CAN_FIRE'])
display_by_rule('WILL_FIRE', sim['WILL_FIRE'])
display_by_rule('FORCE_FIRE', sim['FORCE_FIRE'])
display_by_rule('BLOCK_FIRE', sim['BLOCK_FIRE'])

print('\nDone')
