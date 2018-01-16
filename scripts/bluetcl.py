#!/usr/bin/env python3

import subprocess
import random
import time
import string
import os
import sys
import warnings
from tclutil import *

class BlueTCLException(Exception):
    """Base class for BlueTCL exceptions."""
    pass

class BlueTCLError(BlueTCLException):
    """bluetcl command failed."""
    def __init__(self, command, error_message, stderr = ''):
        self.command = command
        self.error_message = error_message.strip()
        self.stderr = stderr
        super().__init__(self.__str__())
    def __str__(self):
        msg = 'BlueTCLError raised while executing the command "%s"\n error_message: "%s"' % (self.command, self.error_message)
        if self.stderr:
            msg += '\n stderr: %s' % (self.stderr)
        return msg

class BlueTCLInstanceError(BlueTCLException):
    """blutcl process is in an unexpected state."""
    pass

class BlueTCL:
    """Python interface for executing bluetcl commands.

    You can use this class in two ways:

    1) Create an instance of BlueTCL and strart the bluetcl background process
    by calling the start method. When you are done executing bluetcl code,
    stop the bluetcl background process by calling the stop method.

    Example:
    >> btcl = BlueTCL()
    >> btcl.start()
    >> btcl.eval('Bluetcl::bpackage load mypackagename')
    >> btcl.stop()

    2) Use with notation to create a BlueTCL instance. This will start the
    bluetcl background process automatically and stop it when the with block is
    exited.

    Example:
    >> with BlueTCL() as btcl:
    >>     btcl.eval('Bluetcl::bpackage load mypackagename')

    Refer to the BSV user guide for the list of valid bluetcl commands. This
    guide can be found at $BLUESPECDIR/../doc/BSV/bsv-reference-guide.pdf
    """

    reserved_variable_name = 'reservedbluetcloutputvar'

    def __init__(self):
        self._process = None
        self.last_stderr = None

    def start(self):
        """Start the bluetcl background process."""
        if self._process:
            # TODO: use more descriptive exception
            raise BlueTCLInstanceError('bluetcl instance already running.')
        self._process = subprocess.Popen(
            ['bluetcl'],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)

    def stop(self):
        """Stop the bluetcl background process."""
        if not self._process:
            raise ('no bluetcl instance running.')
        self._process.communicate()
        del self._process
        self._process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def eval(self, command):
        """Execute a single command in bluetcl and return the output string.
        
        If a script containing multiple commands is passed in, the output
        string from the last command is returned.
        """
        if not self._process:
            raise BlueTCLInstanceError('no bluetcl instance running.')

        # unique strings for identifying where output from commands start and finish
        key_string_length = 16
        def gen_unique_string(length = key_string_length):
            return ''.join([ random.choice(string.ascii_letters + string.digits) for x in range(length) ])
        stdout_start_key = gen_unique_string()
        stdout_done_key = gen_unique_string()
        stderr_start_key = gen_unique_string()
        stderr_delimiter_key = gen_unique_string()
        stderr_done_key = gen_unique_string()

        main_tcl_code = '\n'.join(['if { [ catch {',
                command,
                '} %s ] } {' % BlueTCL.reserved_variable_name,
                '    puts -nonewline stderr ' + stderr_delimiter_key,
                '    puts -nonewline stderr $' + BlueTCL.reserved_variable_name,
                '    puts -nonewline stderr ' + stderr_delimiter_key,
                '} else {',
                '    puts -nonewline stdout $' + BlueTCL.reserved_variable_name,
                '}\n'])

        self._process.stdin.write(bytearray('puts -nonewline stdout "' + stdout_start_key + '"\n', 'ascii'))
        self._process.stdin.write(bytearray('puts -nonewline stderr "' + stderr_start_key + '"\n', 'ascii'))
        self._process.stdin.write(bytearray(main_tcl_code, 'ascii'))
        self._process.stdin.write(bytearray('puts -nonewline stdout "' + stdout_done_key + '"\n', 'ascii'))
        self._process.stdin.write(bytearray('puts -nonewline stderr "' + stderr_done_key + '"\n', 'ascii'))
        self._process.stdin.write(bytearray('flush stdout\nflush stderr\n', 'ascii'))
        self._process.stdin.flush()

        stdout = ''
        stderr = ''

        fetching_stdout = True
        fetching_stderr = True
        while fetching_stdout or fetching_stderr:
            if fetching_stdout:
                stdout += self._process.stdout.read1(1).decode('ascii')
            if fetching_stderr:
                stderr += self._process.stderr.read1(1).decode('ascii')
            if stdout.endswith(stdout_done_key):
                fetching_stdout = False
            if stderr.endswith(stderr_done_key):
                fetching_stderr = False

        # remove start keys and done keys
        stdout = stdout[len(stdout_start_key):-len(stdout_done_key)]
        stderr = stderr[len(stdout_start_key):-len(stdout_done_key)]
        stderr_split = stderr.split(stderr_delimiter_key)
        if len(stderr_split) == 3:
            # The tcl command returned a non-zero exit code
            cmd_stderr = stderr_split[0]
            error_message = stderr_split[1]
            unexpected_stderr = stderr_split[2]
            if cmd_stderr:
                warnings.warn('bluetcl command "%s" generated stderr message %s' % (command, repr(cmd_stderr)), stacklevel = 2)
            if unexpected_stderr:
                # This shouldn't happen
                raise RuntimeError('bluetcl command "%s" produced unexpected stderr message %s' % (command, repr(unexpected_stderr)))
            raise BlueTCLError(command, error_message, cmd_stderr)
        elif len(stderr_split) != 1:
            # This also shouldn't happen
            raise RuntimeError('bluetcl command "%s" produced stderr with an unexpected number of stderr delimiter keys. Full stderr message: %s' % (command, repr(stderr)))
        else:
            if stderr:
                warnings.warn('bluetcl command "%s" generated stderr message %s' % (command, repr(stderr)), stacklevel = 2)
        self.last_stderr = stderr
        return stdout 

if __name__ == '__main__':
    # this uses the output from the simple example in the main function of bsvproject.py
    package_name = 'Test'
    top_module = 'mkComplexPipeline'

    # create a bluetcl instance and start it
    bluetcl = BlueTCL()
    bluetcl.start()

    # bluetcl expects a few bsc flags to be set
    bluetcl.eval('Bluetcl::flags set -verilog -p test_bsvproject/bdir:+')

    # execute a few simple commands and return their output
    def run_bluetcl_command(command_name, format_fn = None):
        out = bluetcl.eval(command_name)
        if format_fn:
            out = format_fn(out)
        print(command_name + ' -> ' + str(out) + '\n')
        return out

    run_bluetcl_command('Bluetcl::bpackage load %s' % package_name, tclstring_to_list)
    run_bluetcl_command('Bluetcl::bpackage list', tclstring_to_list)
    run_bluetcl_command('Bluetcl::bpackage depend', tclstring_to_nested_list)
    run_bluetcl_command('Bluetcl::bpackage types %s' % package_name, tclstring_to_list)
    run_bluetcl_command('Bluetcl::defs type %s' % package_name, tclstring_to_list)
    run_bluetcl_command('Bluetcl::defs module %s' % package_name, tclstring_to_list)
    run_bluetcl_command('Bluetcl::defs func %s' % package_name, tclstring_to_nested_list)

    # execute a small script and use "return -level 0" to return a specific value from it
    script_out = bluetcl.eval('''
        Bluetcl::bpackage load %s
        set packages [Bluetcl::bpackage list]
        return -level 0 $packages
        ''' % package_name)
    print('script output = ' + repr(script_out))

    # stop the bluetcl instance
    bluetcl.stop()
