import ctypes

class VerilatorWrapper:
    def __init__(self, sofile):
        self.lib = ctypes.CDLL(sofile)
        num_rules = self.lib.get_num_rules()
        self.rule_names = [''] * num_rules
        get_rule_fn = self.lib.get_rule
        get_rule_fn.restype = ctypes.c_char_p
        for i in range(num_rules):
            self.rule_names[i] = get_rule_fn(i).decode('ascii')
        construct = self.lib.construct
        construct.restype = ctypes.c_void_p
        self.model = construct()

    def __del__(self):
        self.lib.destruct(self.model)
        del self.lib

    def get_num_rules(self):
        return len(self.rule_names)

    def get_rule(self, rule_index):
        return self.rule_names[rule_index]

    def set_CLK(self, new_clk_val):
        return self.lib.set_CLK(self.model, new_clk_val)

    def eval(self):
        return self.lib.eval(self.model)

    def get_CAN_FIRE(self, rule_index):
        return self.lib.get_CAN_FIRE(self.model, rule_index)

    def get_WILL_FIRE(self, rule_index):
        return self.lib.get_WILL_FIRE(self.model, rule_index)

    def get_FORCE_FIRE(self, rule_index):
        return self.lib.get_FORCE_FIRE(self.model, rule_index)

    def get_BLOCK_FIRE(self, rule_index):
        return self.lib.get_BLOCK_FIRE(self.model, rule_index)

    def set_FORCE_FIRE(self, rule_index, new_val):
        return self.lib.set_FORCE_FIRE(self.model, rule_index, new_val)

    def set_BLOCK_FIRE(self, rule_index, new_val):
        return self.lib.set_BLOCK_FIRE(self.model, rule_index, new_val)
