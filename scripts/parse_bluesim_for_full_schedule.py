#!/usr/bin/env python3

import sys
import re

def parse_bluesim_for_full_schedule(bluesim_model_file_name):
    with open(bluesim_model_file_name) as f:
        bluesim_model = f.read()
    will_fire_signals = re.findall(r'if \((.*WILL_FIRE.*)\)', bluesim_model)

    schedule = []
    for will_fire_signal in will_fire_signals:
        # split by '.' and drop first entry since it is always INST_top
        rule_full_name = will_fire_signal.split('.')[1:]
        for i in range(len(rule_full_name)):
            if i == len(rule_full_name) - 1:
                # last level
                rule_full_name[i] = rule_full_name[i][len('DEF_WILL_FIRE_'):]
            else:
                # module hierarchy
                rule_full_name[i] = rule_full_name[i][len('INST_'):]
        schedule.append( '.'.join(rule_full_name) )
    return schedule


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('ERROR: this program expects a bluespec-generated bluesim C++ model file as a command-line argument')
    else:
        full_schedule = parse_bluesim_for_full_schedule(sys.argv[1])
        print('\n'.join(full_schedule))
