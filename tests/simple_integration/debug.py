#!/usr/bin/env python3
import sys
sys.path.append("../../scripts")
import frontend

a = frontend.BluespecREPL("obj_dir/VmkSimpleIntegration")
a.run_bsc(1)
a.run_random_schedule(5,printRulesFired=True)
