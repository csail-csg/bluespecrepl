#!/usr/bin/env python3
from bluespecrepl.verilator_wrapper import VerilatorWrapper

a = VerilatorWrapper('obj_dir/VmkSimpleHierarchy')

def status_summary():
    summary = [['rule name', 'CAN_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE', 'WILL_FIRE']]
    for i in range(a.get_num_rules()):
        summary.append([a.get_rule(i), str(a.get_CAN_FIRE(i)), str(a.get_BLOCK_FIRE(i)), str(a.get_FORCE_FIRE(i)), str(a.get_WILL_FIRE(i))])
    max_width = [0] * len(summary[0])
    for row in summary:
        for col_index in range(len(row)):
            if len(row[col_index]) > max_width[col_index]:
                max_width[col_index] = len(row[col_index])
    for row in summary:
        print('    ', end='')
        for col_index in range(len(row)):
            print(row[col_index].ljust(max_width[col_index]+1), end='')
        print('')

def tick(n):
    for i in range(n):
        a.eval()
        print('ticking with the following signals...')
        status_summary()
        a.eval()
        a.set_CLK(0)
        a.eval()
        a.set_CLK(1)
        a.eval()


tick(1)
status_summary()

counter_rule = 3
for i in range(a.get_num_rules()):
    if i == counter_rule:
        a.set_BLOCK_FIRE(i, 0)
    else:
        a.set_BLOCK_FIRE(i, 1)

tick(11)

# deq_rule = 1 and 4
deq_rules = [1, 4]
for i in range(a.get_num_rules()):
    if i in deq_rules:
        a.set_BLOCK_FIRE(i, 0)
    else:
        a.set_BLOCK_FIRE(i, 1)

tick(3)
