#!/usr/bin/env python3

import sys
import os
import re
import glob
import subprocess
import shutil
import jinja2
import tclwrapper
import warnings
import verilog_mutator
import pyverilatorbsv
from tclutil import *

_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
_jinja2_env = jinja2.Environment(loader = jinja2.FileSystemLoader(_template_path))
_bspec_project_file_template = _jinja2_env.get_template('template.bspec')

class BSVProject:
    """Bluespec System Verilog Project class.

    This class allows for BSV projects to be manipulated from Python. Projects
    can be created by the __init__ function or they can be imported from
    *.bspec files. Projects can also be exported to *.bspec files.

    Each project has the following project configuration variables:
    path -- list of directories containing BSV source files
    build_dir -- output directory for .bo/.ba files
    sim_dir -- output directory for bluesim files (except the executable)
    verilog_dir -- output directory for verilog files
    info_dir -- output directory for miscelanious info files
    f_dir -- base directory used for relative paths in BSV files
    sim_exe -- name for bluesim executable
    bsc_options -- list of additional command line arguments for bsc
    rts_options -- list of RTS command line arguments for bsc
    """

    # paths that are always appended to the end of the user-specified paths
    default_paths = ['%/Prelude', '%/Libraries', '%/Libraries/BlueNoC']
    # automatically add these to self.bsc_options in the __init__ function
    default_bsc_options = ['-aggressive-conditions', '-keep-fires']

    def __init__(self, top_file = None, top_module = None, path = [], build_dir = 'build_dir', sim_dir = 'sim_dir', verilog_dir = 'verilog_dir', info_dir = 'info_dir', f_dir = '.', sim_exe = 'sim.out', bsc_options = [], rts_options = [], bspec_file = None):
        if bspec_file is not None:
            import_bspec_project_file(bspec_file)
        else:
            if top_file is None or top_module is None:
                raise ValueError('Either top_file and top_module need to be defined, or bspec_file needs to be defined')
            # Project Definition
            self.top_file = top_file
            self.top_module = top_module
            # Path
            self.path = path
            # Directories
            self.build_dir = build_dir
            self.sim_dir = sim_dir
            self.verilog_dir = verilog_dir
            self.info_dir = info_dir
            self.f_dir = f_dir
            # Options
            self.sim_exe = sim_exe
            for arg in BSVProject.default_bsc_options:
                if arg not in bsc_options:
                    bsc_options.append(arg)
            self.bsc_options = bsc_options
            self.rts_options = rts_options

    # command line argument formatting
    def get_dir_args(self, build_dir = None, sim_dir = None, verilog_dir = None, info_dir = None, f_dir = None):
        """Returns formatted bsc arguments for output directories."""
        if build_dir == None:
            build_dir = self.build_dir
        if sim_dir == None:
            sim_dir = self.sim_dir
        if verilog_dir == None:
            verilog_dir = self.verilog_dir
        if info_dir == None:
            info_dir = self.info_dir
        if f_dir == None:
            f_dir = self.f_dir
        for directory in [build_dir, sim_dir, verilog_dir, info_dir, f_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        return ['-bdir', build_dir,
                '-simdir', sim_dir,
                '-vdir', verilog_dir,
                '-info-dir', info_dir,
                '-fdir', f_dir]

    def get_path_arg(self):
        """Returns formatted bsc arguments for the path."""
        return ['-p', ':'.join([self.build_dir] + self.path + BSVProject.default_paths)]

    def get_sim_exe_out_arg(self):
        """Returns formatted bsc argument for the sim exe."""
        dirname = os.path.dirname(self.sim_exe)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        return ['-o', self.sim_exe]

    # compilation functions
    def compile_verilog(self, out_folder = None, extra_bsc_args = []):
        """Compiles the project to verilog.

        If out_folder is specified, the verilog is written there. Otherwise the
        verilog is written to the projects verilog_dir.
        """
        # add the -elab flag to ensure .ba files are generated during compilation
        bsc_command = ['bsc', '-verilog', '-elab'] + self.bsc_options + extra_bsc_args + self.get_dir_args(verilog_dir = out_folder) + self.get_path_arg() + ['-g', self.top_module, '-u', self.top_file]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')

    def compile_bluesim(self, out_folder = None, extra_bsc_args = []):
        """Compiles the project to a bluesim executable.

        If out_folder is specified, the bluesim intermediate files are written
        there. Otherwise the files are written to sim_dir.
        """
        bsc_command = ['bsc', '-sim'] + self.bsc_options + extra_bsc_args + self.get_dir_args(sim_dir = out_folder) + self.get_path_arg() + ['-g', self.top_module, '-u', self.top_file]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')
        bsc_command = ['bsc', '-sim'] + self.bsc_options + extra_bsc_args + self.get_dir_args(sim_dir = out_folder) + self.get_path_arg() + self.get_sim_exe_out_arg() + ['-e', self.top_module]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')

    def gen_python_repl(self, scheduling_control = False, verilator_dir = 'verilator_dir'):
        """Compiles the project to a python BluespecREPL compatable verilator executable."""
        extra_bsc_args = []
        if scheduling_control:
            extra_bsc_args.append('-no-opt-ATS')
        self.compile_verilog(extra_bsc_args = extra_bsc_args)

        # copy verilog files to verilator dir
        if not os.path.exists(verilator_dir):
            os.makedirs(verilator_dir)
        for name in os.listdir(self.verilog_dir):
            base, extension = os.path.splitext(name)
            if extension.lower() == '.v':
                shutil.copy(os.path.join(self.verilog_dir, name), os.path.join(verilator_dir, name))

        verilog_file = os.path.join(verilator_dir, self.top_module + '.v')
        rules = []
        if scheduling_control:
            # modify the compiled verilog to add scheduling control signals
            mutator = verilog_mutator.VerilogMutator(verilog_file)
            mutator.expose_internal_scheduling_signals()
            mutator.write_verilog(verilog_file)
            rules = mutator.get_rules_in_scheduling_order()

        bsv_verilog_dir = os.path.join(os.environ['BLUESPECDIR'], 'Verilog')
        return pyverilatorbsv.PyVerilatorBSV.build(
                verilog_file,
                verilog_path = [verilator_dir, bsv_verilog_dir],
                build_dir = verilator_dir,
                rules = rules,
                module_name = self.top_module,
                bsc_build_dir = self.build_dir)

    def clean(self):
        """Deletes output from project compilation."""
        cleaning_targets = [
                (self.build_dir, ['.ba', '.bo']),
                (self.sim_dir, ['.cxx', '.h', '.o']),
                (self.verilog_dir, ['.v']),
                (self.info_dir, [])]
        # This function should delete:
        #   *.ba, *.bo from build_dir
        #   *.cxx, *.h, *.o from sim_dir
        #   *.v from verilog_dir
        #   ? from info_dir
        #   sim_exe
        for path, extensions in cleaning_targets:
            for name in os.listdir(path):
                if os.path.splitext(name)[1].lower() in extensions:
                    os.remove(os.path.join(path, name))
            try:
                os.rmdir(path)
            except OSError:
                # ignore errors
                pass
        os.remove(self.sim_exe)

    # import/export methods
    def import_bspec_project_file(filename):
        """Import project settings from a .bspec file"""
        params = {}
        with open(filename) as f:
            lines = f.readlines()
        for line in lines:
            match = re.match(r'set PROJECT\((.*?)\) "(.*)"', line)
            if match:
                params[match.group(1)] = match.group(2)
        self.import_bspec_config_params(params)

    def export_bspec_project_file(self, filename):
        """Export project settings to a .bspec file"""
        params = self.export_bspec_config_params()
        # use jinja2 and the template in templates/template.bspec to create the project file
        bspec_project_text = _bspec_project_file_template.render(params)
        with open(filename, 'w') as f:
            f.write(bspec_project_text)

    def import_bspec_config_params(self, params):
        """Imports project settings from parameters defined in a *.bspec file"""
        self.top_file = params['TOP_FILE']
        self.top_module = params['TOP_MODULE']
        self.path = list(tclstring_to_list(params['PATHS']))
        self.build_dir = params['COMP_BDIR']
        self.sim_dir = params['COMP_SIMDIR']
        self.verilog_dir = params['COMP_VDIR']
        self.info_dir = params['COMP_INFO_DIR']
        self.f_dir = params['CURRENT_DIR']
        self.sim_exe = os.path.join(params['LINK_OUTDIR'], params['LINK_OUTNAME'])
        self.bsc_options = params['COMP_BSC_OPTIONS'].split(' ')
        link_bsc_options = params['LINK_BSC_OPTIONS'].split(' ')
        for opt in link_bsc_options:
            if opt not in self.bsc_options:
                self.bsc_options.append(opt)
        self.rts_options = params['COMP_RTS_OPTIONS'].split(' ')

        # strip default path arguments from self.path
        for path in BSVProject.default_paths:
            if path in self.path:
                self.path.remove(path)

    def export_bspec_config_params(self):
        """Exports project settings to a dict of *.bspec file parameters"""
        params = {}
        params['TOP_FILE'] = self.top_file
        params['TOP_MODULE'] = self.top_module
        params['PATHS'] = list_to_tclstring([self.build_dir] + self.path + BSVProject.default_paths)
        params['COMP_BDIR'] = self.build_dir
        params['COMP_SIMDIR'] = self.sim_dir
        params['COMP_VDIR'] = self.verilog_dir
        params['COMP_INFO_DIR'] = self.info_dir
        params['CURRENT_DIR'] = self.f_dir
        link_outdir = os.path.dirname(self.sim_exe)
        if link_outdir == '':
            link_outdir = '.'
        params['LINK_OUTDIR'] = link_outdir
        params['LINK_OUTNAME'] = os.path.basename(self.sim_exe)
        params['COMP_BSC_OPTIONS'] = ' '.join(self.bsc_options)
        params['LINK_BSC_OPTIONS'] = ' '.join(self.bsc_options)
        params['COMP_RTS_OPTIONS'] = ' '.join(self.rts_options)
        return params

    # Advanced Functions
    #####################
    def get_hierarchy(self, module_name = None):
        if module_name is None:
            module_name = self.top_module
        hierarchy = {}
        modules_to_add = [module_name]
        with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
            bluetcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            while len(modules_to_add) > 0:
                curr_module_name = modules_to_add.pop()
                try:
                    bluetcl.eval('Bluetcl::module load ' + curr_module_name)
                    hierarchy[curr_module_name] = []
                    user_or_prim, submodules, functions = tclstring_to_nested_list(bluetcl.eval('Bluetcl::module submods ' + curr_module_name))
                    if user_or_prim == 'user':
                        for instance_name, submodule_name in submodules:
                            if submodule_name not in hierarchy and submodule_name not in modules_to_add:
                                modules_to_add.append(submodule_name)
                            hierarchy[curr_module_name].append((instance_name, submodule_name))
                except tclwrapper.TCLWrapperError as e:
                    # couldn't load modules, typically the case for primitive modules such as FIFOs
                    hierarchy[curr_module_name] = None
        return hierarchy

    def get_module_schedule(self, module_name = None):
        if module_name is None:
            module_name = self.top_module
        with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
            bluetcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            bluetcl.eval('Bluetcl::module load ' + module_name)
            return tclstring_to_list(bluetcl.eval('Bluetcl::schedule execution ' + module_name))

    def get_complete_schedule(self):
        """Returns the complete schedule for the top module.

        The schedule is a combination of top-level interface methods, top-level
        rules, and submodule rules. This requires compiling for bluesim.
        """
        # The complete schedule can be inferred by this file
        bluesim_model_file = os.path.join(self.sim_dir, 'model_%s.cxx' % self.top_module)
        # bluesim compilation is erquired to generate the bluesim_model_file
        self.compile_bluesim()

        # regex patterns
        # start and end of schedule_posedge_CLK function
        # not exact, but good enough
        fn_start_regex = r'^static void schedule_posedge_CLK'
        fn_end_regex = r'^[^\s]'
        # schedule pattern
        schedule_regex = r'if \(INST_top.([^)]*)\)'
        with open(bluesim_model_file, 'r') as f:
            complete_schedule = []
            # skip to start of schedule_posedge_CLK function
            line = f.readline()
            while not re.search(fn_start_regex, line):
                line = f.readline()
            line = f.readline()
            while not re.search(fn_end_regex, line):
                match = re.search(schedule_regex, line)
                if match:
                    # remove INST_ and DEF_WILL_FIRE_ from the hierarchy
                    hierarchy = match.group(1).split('.')
                    for i in range(len(hierarchy)):
                        if i == len(hierarchy) - 1:
                            if not hierarchy[i].startswith('DEF_WILL_FIRE_'):
                                raise ValueError("full schedule hierarchy has unexpected element")
                            hierarchy[i] = hierarchy[i][len('DEF_WILL_FIRE_'):]
                        else:
                            if not hierarchy[i].startswith('INST_'):
                                raise ValueError("full schedule hierarchy has unexpected element")
                            hierarchy[i] = hierarchy[i][len('INST_'):]
                    complete_schedule.append(tuple(hierarchy))
                line = f.readline()
        return complete_schedule

if __name__ == '__main__':
    bsv_module_text='''(* noinline *)
    function Bit#(8) do_addition( Bit#(8) a, Bit#(8) b );
        return a + b;
    endfunction'''
    module_name = 'module_do_addition'
    bsv_file = 'Test.bsv'

    warnings.simplefilter('ignore')

    if not os.path.exists('test_bsvproject'):
        os.makedirs('test_bsvproject')
    os.chdir('test_bsvproject')

    with open(bsv_file, 'w') as f:
        f.write(bsv_module_text)

    project = BSVProject(top_module = module_name, top_file = bsv_file)
    repl = project.gen_python_repl()
    tests = [(0, 0), (1, 2), (3, 6), (255, 1), (255, 2)]
    for x, y in tests:
        repl['do_addition_a'] = x
        repl['do_addition_b'] = y
        out = repl['do_addition']
        print('%d + %d = %d' % (x, y, out))
