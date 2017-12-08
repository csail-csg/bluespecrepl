#!/usr/bin/env python3

import ctypes

lib = ctypes.CDLL('obj_dir/VmkSimpleIntegration')

lib.construct()

num_rules = lib.get_num_rules()
print('num_rules = ' + str(num_rules))

get_rule_fn = lib.get_rule
get_rule_fn.restype = ctypes.c_char_p
print('using get_rule(x):')
for i in range(num_rules):
    print('rule[%d] = %s' % (i, get_rule_fn(i).decode('ascii')))

def tick(n):
    for i in range(n):
        lib.eval()
        lib.set_CLK(1)
        lib.eval()
        lib.set_CLK(0)
        lib.eval()

tick(10)

x = lib.get_CAN_FIRE(3)
print('always_ready_and_enabled.CAN_FIRE = ' + str(x))
x = lib.get_WILL_FIRE(3)
print('always_ready_and_enabled.WILL_FIRE = ' + str(x))
x = lib.get_FORCE_FIRE(3)
print('always_ready_and_enabled.FORCE_FIRE = ' + str(x))
x = lib.get_BLOCK_FIRE(3)
print('always_ready_and_enabled.BLOCK_FIRE = ' + str(x))

print('')
print('blocking always_ready_and_enabled...')
lib.set_BLOCK_FIRE(3, 1)

print('')
x = lib.get_CAN_FIRE(3)
print('always_ready_and_enabled.CAN_FIRE = ' + str(x))
x = lib.get_WILL_FIRE(3)
print('always_ready_and_enabled.WILL_FIRE = ' + str(x))
x = lib.get_FORCE_FIRE(3)
print('always_ready_and_enabled.FORCE_FIRE = ' + str(x))
x = lib.get_BLOCK_FIRE(3)
print('always_ready_and_enabled.BLOCK_FIRE = ' + str(x))

print('')
print('evaluating...')
lib.eval()

print('')
x = lib.get_CAN_FIRE(3)
print('always_ready_and_enabled.CAN_FIRE = ' + str(x))
x = lib.get_WILL_FIRE(3)
print('always_ready_and_enabled.WILL_FIRE = ' + str(x))
x = lib.get_FORCE_FIRE(3)
print('always_ready_and_enabled.FORCE_FIRE = ' + str(x))
x = lib.get_BLOCK_FIRE(3)
print('always_ready_and_enabled.BLOCK_FIRE = ' + str(x))

print('')
print('ticking clock...')
tick(1)

print('')
x = lib.get_CAN_FIRE(3)
print('always_ready_and_enabled.CAN_FIRE = ' + str(x))
x = lib.get_WILL_FIRE(3)
print('always_ready_and_enabled.WILL_FIRE = ' + str(x))
x = lib.get_FORCE_FIRE(3)
print('always_ready_and_enabled.FORCE_FIRE = ' + str(x))
x = lib.get_BLOCK_FIRE(3)
print('always_ready_and_enabled.BLOCK_FIRE = ' + str(x))

print('')
print('blocking all rules...')
for i in range(5):
    lib.set_BLOCK_FIRE(i, 1)

print('')
print('ticking clock...')
tick(1)

print('')
print('ticking clock...')
tick(1)

lib.destruct()
