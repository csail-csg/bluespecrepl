#!/usr/bin/env python3

class VCD:
    """Class for reading VCD files."""

    def __init__(self, filename):
        self.filename = filename
        self._parse_full_vcd()

    def _parse_full_vcd(self):
        # name -> code
        self.signal_codes = {}
        # code -> value
        self.signal_values = {}
        with open(self.filename, 'r') as f:
            vcd_tokens = f.read().split()
            i = 0
            scope = []
            while i < len(vcd_tokens):
                if vcd_tokens[i][0] == '$' and vcd_tokens[i] != '$end':
                    # find next end
                    next_end = i + 1
                    while vcd_tokens[next_end] != '$end':
                        next_end += 1

                    if vcd_tokens[i] == '$var':
                        var_type = vcd_tokens[i+1]
                        var_width = vcd_tokens[i+2]
                        var_identifier = vcd_tokens[i+3]
                        # do not includ anything after the space in var_name
                        # eg: "pc [31:0]" is just stored as "pc"
                        var_name = vcd_tokens[i+4]
                        # var_name = ' '.join(vcd_tokens[i+4:next_end])
                        # add variable
                        full_var_name = '/' + '/'.join(scope) + '/' + var_name
                        self.signal_codes[full_var_name] = var_identifier
                        self.signal_values[var_identifier] = None

                    elif vcd_tokens[i] == '$scope':
                        scope_type = vcd_tokens[i+1]
                        scope_name = vcd_tokens[i+2]
                        # update scope
                        scope.append(scope_name)

                    elif vcd_tokens[i] == '$upscope':
                        # update scope
                        scope.pop()

                    i = next_end + 1

                else:
                    if vcd_tokens[i][0] == '#':
                        self.curr_time = int(vcd_tokens[i][1:])
                        i += 1
                    elif vcd_tokens[i][0] in ['0', '1', 'x', 'X', 'z', 'Z']:
                        if vcd_tokens[i][0] == '0':
                            value = 0
                        elif vcd_tokens[i][0] == '1':
                            value = 1
                        else:
                            value = None
                        self.signal_values[vcd_tokens[i][1]] = value
                        i += 1
                    else:
                        if vcd_tokens[i][0].lower() == 'b':
                            value = int( vcd_tokens[i][1:], base = 2 )
                        elif vcd_tokens[i][0].lower() == 'r':
                            value = float( vcd_tokens[i][1:] )
                        else:
                            value = None
                            raise ValueError('Unexpected simulation token: ' + vcd_tokens[i])
                        self.signal_values[vcd_tokens[i+1]] = value
                        i += 2

    def reload(self):
        # TODO: do something clever with self.curr_time
        self._parse_full_vcd()

    def get_signals(self):
        """Get the list of signals found in the VCD file."""
        signals = list(self.signal_codes.keys())
        signals.sort()
        return signals

    def get_signal_value(self, signal_name):
        """Get the most recent value for the specified signal."""
        return self.signal_values[self.signal_codes[signal_name]]

if __name__ == '__main__':
    import sys
    filename = sys.argv[1]
    print('VCD File: ' + filename)
    vcd = VCD(filename)
    signals = vcd.get_signals()
    print('Final Values:')
    for signal in signals:
        print(signal + ' = ' + str(vcd.get_signal_value(signal)))

