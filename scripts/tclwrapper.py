#!/usr/bin/env python3

import subprocess
import random
import time
import string
import os
import sys
import warnings
from tclutil import *

class TCLWrapperException(Exception):
    """Base class for TCLWrapper exceptions."""
    pass

class TCLWrapperError(TCLWrapperException):
    """tcl command failed."""
    def __init__(self, command, error_message, stderr = ''):
        self.command = command
        self.error_message = error_message.strip()
        self.stderr = stderr
        super().__init__(self.__str__())
    def __str__(self):
        msg = 'TCLWrapperError raised while executing the command "%s"\n error_message: "%s"' % (self.command, self.error_message)
        if self.stderr:
            msg += '\n stderr: %s' % (self.stderr)
        return msg

class TCLWrapperInstanceError(TCLWrapperException):
    """tcl process is in an unexpected state."""
    pass

class TCLWrapper:
    """Python interface for executing tcl commands in a specified tcl-based tool.

    You can use this class in two ways:

    1) Create an instance of TCLWrapper and strart the desired tcl background
    process by calling the start method. When you are done executing tcl code,
    stop the tcl background process by calling the stop method.

    Example:
    >> btcl = TCLWrapper('bluetcl')
    >> btcl.start()
    >> btcl.eval('Bluetcl::bpackage load mypackagename')
    >> btcl.stop()

    2) Use with notation to create a TCLWrapper instance. This will start the
    tcl background process automatically and stop it when the with block is
    exited.

    Example:
    >> with TCLWrapper('bluetcl') as btcl:
    >>     btcl.eval('Bluetcl::bpackage load mypackagename')
    """

    reserved_variable_name = 'reservedtcloutputvar'

    def __init__(self, tcl_exe = 'tclsh'):
        """Creates a TCLWrapper for the specified tcl executable."""
        self._process = None
        self.last_stderr = None
        self.tcl_exe = tcl_exe

    def start(self):
        """Start the tcl background process."""
        if self._process:
            # TODO: use more descriptive exception
            raise TCLWrapperInstanceError('tcl instance already running.')
        self._process = subprocess.Popen(
            [self.tcl_exe],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)

    def stop(self):
        """Stop the tcl background process."""
        if not self._process:
            raise ('no tcl instance running.')
        try:
            self._process.communicate(timeout = 1)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.communicate()
        del self._process
        self._process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def eval(self, command, to_list = False):
        """Execute a single command in tcl and return the output string.
        
        If a script containing multiple commands is passed in, the output
        string from the last command is returned.
        """
        if not self._process:
            raise TCLWrapperInstanceError('no tcl instance running.')

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
                '} %s ] } {' % TCLWrapper.reserved_variable_name,
                '    puts -nonewline stderr ' + stderr_delimiter_key,
                '    puts -nonewline stderr $' + TCLWrapper.reserved_variable_name,
                '    puts -nonewline stderr ' + stderr_delimiter_key,
                '} else {',
                '    puts -nonewline stdout $' + TCLWrapper.reserved_variable_name,
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
                warnings.warn('tcl command "%s" generated stderr message %s' % (command, repr(cmd_stderr)), stacklevel = 2)
            if unexpected_stderr:
                # This shouldn't happen
                raise RuntimeError('tcl command "%s" produced unexpected stderr message %s' % (command, repr(unexpected_stderr)))
            raise TCLWrapperError(command, error_message, cmd_stderr)
        elif len(stderr_split) != 1:
            # This also shouldn't happen
            raise RuntimeError('tcl command "%s" produced stderr with an unexpected number of stderr delimiter keys. Full stderr message: %s' % (command, repr(stderr)))
        else:
            if stderr:
                warnings.warn('tcl command "%s" generated stderr message %s' % (command, repr(stderr)), stacklevel = 2)
        self.last_stderr = stderr
        if to_list:
            stdout = tclstring_to_list(stdout)
        return stdout 

if __name__ == '__main__':
    # this uses the output from the simple example in the main function of bsvproject.py
    package_name = 'Test'
    top_module = 'mkComplexPipeline'

    # create a bluetcl instance and start it
    tcl = TCLWrapper('bluetcl')
    tcl.start()

    # tcl expects a few bsc flags to be set
    tcl.eval('Bluetcl::flags set -verilog -p test_bsvproject/bdir:+')

    # execute a few simple commands and return their output
    def run_tcl_command(command_name, format_fn = None):
        out = tcl.eval(command_name)
        if format_fn:
            out = format_fn(out)
        print(command_name + ' -> ' + str(out) + '\n')
        return out

    run_tcl_command('Bluetcl::bpackage load %s' % package_name, tclstring_to_list)
    run_tcl_command('Bluetcl::bpackage list', tclstring_to_list)
    run_tcl_command('Bluetcl::bpackage depend', tclstring_to_nested_list)
    run_tcl_command('Bluetcl::bpackage types %s' % package_name, tclstring_to_list)
    run_tcl_command('Bluetcl::defs type %s' % package_name, tclstring_to_list)
    run_tcl_command('Bluetcl::defs module %s' % package_name, tclstring_to_list)
    run_tcl_command('Bluetcl::defs func %s' % package_name, tclstring_to_nested_list)

    # execute a small script and use "return -level 0" to return a specific value from it
    script_out = tcl.eval('''
        Bluetcl::bpackage load %s
        set packages [Bluetcl::bpackage list]
        return -level 0 $packages
        ''' % package_name)
    print('script output = ' + repr(script_out))

    # stop the tcl instance
    tcl.stop()
