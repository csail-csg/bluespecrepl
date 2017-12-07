import frontend

a = frontend.BluespecREPL("obj_dir/VmkSimpleIntegration","build","mkSimpleIntegration")
a.run_bsc(10)
a.run_random_schedule(5,printRulesFired=True)
