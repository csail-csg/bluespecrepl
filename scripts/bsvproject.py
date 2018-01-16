#!/usr/bin/env python3

import sys
import os
import re
import glob
import subprocess
import jinja2
import bluetcl
import warnings
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

    default_paths = ['%/Prelude', '%/Libraries', '%/Libraries/BlueNoC']
    default_arguments = ['-aggressive-conditions', '-keep-fires']

    def __init__(self, top_file = None, top_module = None, path = [], build_dir = '.', sim_dir = '.', verilog_dir = '.', info_dir = '.', f_dir = '.', sim_exe = 'sim.out', bsc_options = [], rts_options = [], bspec_file = None):
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
            for arg in BSVProject.default_arguments:
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
        if not os.path.exists(os.path.dirname(self.sim_exe)):
            os.makedirs(os.path.dirname(self.sim_exe))
        return ['-o', self.sim_exe]

    # compilation functions
    def compile_verilog(self, out_folder = None):
        """Compiles the project to verilog.

        If out_folder is specified, the verilog is written there. Otherwise the
        verilog is written to the projects verilog_dir.
        """
        bsc_command = ['bsc', '-verilog', '-elab', '-keep-fires', '-no-opt-ATS'] + self.get_dir_args(verilog_dir = out_folder) + self.get_path_arg() + ['-g', self.top_module, '-u', self.top_file]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')

    def compile_bluesim(self, out_folder = None):
        """Compiles the project to a bluesim executable.

        If out_folder is specified, the bluesim intermediate files are written
        there. Otherwise the files are written to sim_dir.
        """
        bsc_command = ['bsc', '-sim', '-keep-fires'] + self.get_dir_args(sim_dir = out_folder) + self.get_path_arg() + ['-g', self.top_module, '-u', self.top_file]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')
        bsc_command = ['bsc', '-sim', '-keep-fires'] + self.get_dir_args(sim_dir = out_folder) + self.get_path_arg() + ['-e', self.top_module]
        exit_code = subprocess.call(bsc_command)
        if exit_code != 0:
            raise Exception('Bluespec Compiler failed compilation')

    def clean(self):
        """Deletes output from project compilation."""
        # This function should delete:
        #   *.ba, *.bo from build_dir
        #   *.cxx, *.o, *.h, etc. from sim_dir
        #   *.v from verilog_dir
        #   ? from info_dir
        #   sim_exe
        raise NotImplementedError('clean is not implemented yet')

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
        params['LINK_OUTDIR'] = os.path.dirname(self.sim_exe)
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
        with bluetcl.BlueTCL() as btcl:
            btcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            while len(modules_to_add) > 0:
                curr_module_name = modules_to_add.pop()
                try:
                    btcl.eval('Bluetcl::module load ' + curr_module_name)
                    hierarchy[curr_module_name] = []
                    user_or_prim, submodules, functions = tclstring_to_nested_list(btcl.eval('Bluetcl::module submods ' + curr_module_name))
                    if user_or_prim == 'user':
                        for instance_name, submodule_name in submodules:
                            if submodule_name not in hierarchy and submodule_name not in modules_to_add:
                                modules_to_add.append(submodule_name)
                            hierarchy[curr_module_name].append((instance_name, submodule_name))
                except bluetcl.BlueTCLError as e:
                    # couldn't load modules, typically the case for primitive modules such as FIFOs
                    hierarchy[curr_module_name] = None
        return hierarchy

    def get_module_schedule(self, module_name = None):
        if module_name is None:
            module_name = self.top_module
        # TODO: implement this function
        with bluetcl.BlueTCL() as btcl:
            btcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            btcl.eval('Bluetcl::module load ' + module_name)
            return tclstring_to_list(btcl.eval('Bluetcl::schedule execution ' + module_name))

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
    module_name = 'mkComplexRuleScheduling'
    bsv_file = 'Test.bsv'
    bsv_module_text = '''
import FIFO::*;

(* synthesize *)
module mkComplexRuleScheduling(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkComplexPipeline;
    FIFO#(Bit#(8)) middle <- mkComplexPipeline;
    FIFO#(Bit#(8)) out <- mkComplexPipeline;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule

(* synthesize *)
module mkComplexPipeline(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkPipeline;
    FIFO#(Bit#(8)) middle <- mkPipeline;
    FIFO#(Bit#(8)) out <- mkPipeline;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule

(* synthesize *)
module mkPipeline(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkLFIFO;
    FIFO#(Bit#(8)) middle <- mkLFIFO;
    FIFO#(Bit#(8)) out <- mkLFIFO;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule
    '''

    warnings.simplefilter('ignore')

    if not os.path.exists('test_bsvproject'):
        os.makedirs('test_bsvproject')
    os.chdir('test_bsvproject')

    with open(bsv_file, 'w') as f:
        f.write(bsv_module_text)

    project = BSVProject( top_module = module_name, top_file = bsv_file, build_dir = 'bdir', sim_dir = 'simdir', verilog_dir = 'vdir' )
    project.compile_verilog()
    project.compile_bluesim()
    hierarchy = project.get_hierarchy()
    print('\nhierarchy = %s\n' % str(hierarchy))
    schedule = project.get_module_schedule()
    print('schedule = %s\n' % str(schedule))
    project.export_bspec_project_file('test.bspec')
    print('exported test.bspec project file to ' + os.path.join(os.path.abspath(os.curdir), 'test.bspec'))
