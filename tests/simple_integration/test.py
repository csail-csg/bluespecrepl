#!/usr/bin/env python3

import ctypes

lib = ctypes.CDLL('obj_dir/VmkSimpleIntegration')

lib.construct()
CAN_FIRE_RL_same_guard_1 = lib.get_CAN_FIRE_RL_same_guard_1()

print('CAN_FIRE_RL_same_guard_1 = ' + str(CAN_FIRE_RL_same_guard_1))

lib.destruct()
