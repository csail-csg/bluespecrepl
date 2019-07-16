import sys
import os
import re
import glob
import subprocess
import shutil
import warnings
import tclwrapper
from tclwrapper.tclutil import *
import bluespecrepl.verilog_mutator as verilog_mutator
import bluespecrepl.pyverilatorbsv as pyverilatorbsv

class BSVProject:
    """Bluespec System Verilog Project class.

    This class allows for BSV projects to be manipulated from Python. Projects
    can be created by the __init__ function or they can be imported from
    *.bspec files. Projects can also be exported to *.bspec files.

    Each project has the following project configuration variables:
    bsv_path -- list of directories containing BSV source files
    v_path -- list of directories containing Verilog source files
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
    default_paths = ['+']
    # automatically add these to self.bsc_options in the __init__ function
    default_bsc_options = ['-aggressive-conditions', '-keep-fires']

    def __init__(self, top_file = None, top_module = None, bsv_path = [], v_path = None, build_dir = 'build_dir', sim_dir = 'sim_dir', verilog_dir = 'verilog_dir', info_dir = 'info_dir', f_dir = '.', sim_exe = 'sim.out', bsc_options = [], rts_options = [], bspec_file = None):
        if bspec_file is not None:
            self.import_bspec_project_file(bspec_file)
        else:
            if top_file is None or top_module is None:
                raise ValueError('Either top_file and top_module need to be defined, or bspec_file needs to be defined')
            # Project Definition
            self.top_file = top_file
            self.top_module = top_module
            # Path
            self.bsv_path = bsv_path.copy()
            if v_path is not None:
                self.v_path = v_path
            else:
                # default verilog directory
                self.v_path = [ os.path.join( os.environ['BLUESPECDIR'], 'Verilog' ) ]
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
            self.bsc_options = bsc_options.copy()
            self.rts_options = rts_options.copy()
        # stuctures that hold metadata obtained from bluetcl
        self.packages = None
        self.modules = None

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
        # The bluespec compiler automatically adds build_dir to the front of the path, but bluetcl does not,
        # so we add it manually and get a warning from the bluespec compiler about redundant folders in the path
        return ['-p', ':'.join([self.build_dir] + self.bsv_path + BSVProject.default_paths)]

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
        # .ba files are used by bluetcl to get information about the design
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
        verilator_verilog_files = {} # map from module name to verilog file
        if not os.path.exists(verilator_dir):
            os.makedirs(verilator_dir)
        for name in os.listdir(self.verilog_dir):
            base, extension = os.path.splitext(name)
            if extension.lower() == '.v':
                shutil.copy(os.path.join(self.verilog_dir, name), os.path.join(verilator_dir, name))
                verilator_verilog_files[base] = os.path.join(verilator_dir, name)

        verilog_file = os.path.join(verilator_dir, self.top_module + '.v')
        rules = []
        if scheduling_control:
            # modify the compiled verilog to add scheduling control signals
            # this is done hierarchically from the leaf modules to the top module
            mutators = { module : verilog_mutator.VerilogMutator(module_verilog_file) for module, module_verilog_file in verilator_verilog_files.items() }
            submodules = { module : mutator.get_submodules() for module, mutator in mutators.items() }
            modules_to_mutate = list(verilator_verilog_files.keys())
            num_rules_per_module = {}
            rule_names_per_module = {}
            while len(modules_to_mutate) != 0:
                module_to_mutate = None
                for module in modules_to_mutate:
                    good_candidate = True
                    for instance_name, instance_module in submodules[module]:
                        if instance_module in modules_to_mutate:
                            good_candidate = False
                    if good_candidate:
                        module_to_mutate = module
                        break
                if module_to_mutate is not None:
                    mutator = mutators[module_to_mutate]
                    num_rules = mutator.expose_internal_scheduling_signals(num_rules_per_module = num_rules_per_module)
                    mutator.write_verilog(verilator_verilog_files[module])
                    rules = mutator.get_rules_in_scheduling_order()
                    num_rules_per_module[module_to_mutate] = num_rules
                    # get list of rule names
                    full_module_rule_names = []
                    for sched_item in mutator.get_default_scheduling_order():
                        if sched_item.startswith('RL_'):
                            full_module_rule_names.append(sched_item)
                        elif sched_item.startswith('MODULE_'):
                            submodule_instance_name = sched_item[len('MODULE_'):]
                            submodule_type = [y for x, y in submodules[module_to_mutate] if x == submodule_instance_name][0]
                            if submodule_type not in rule_names_per_module:
                                # this submodule has no known rules
                                continue
                            submodule_rule_names = [submodule_instance_name + '__DOT__' + x for x in rule_names_per_module[submodule_type]]
                            full_module_rule_names += submodule_rule_names
                        else:
                            raise Exception('Unsupported scheuling item type')
                    rule_names_per_module[module_to_mutate] = full_module_rule_names
                    rule_order = mutator.get_default_scheduling_order()
                    modules_to_mutate.remove(module_to_mutate)
                else:
                    raise Exception("Adding scheduling control failed. Can't find next module to mutate")
            # get rule names
            rules = rule_names_per_module[self.top_module]

        return pyverilatorbsv.PyVerilatorBSV.build(
                verilog_file,
                verilog_path = [verilator_dir] + self.v_path,
                build_dir = verilator_dir,
                rules = rules,
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
        try:
            os.remove(self.sim_exe)
        except OSError:
            # ignore errors
            pass

    # import/export methods
    def import_bspec_project_file(self, filename):
        """Import project settings from a .bspec file.

        This does not import v_path."""
        params = {}
        with open(filename) as f:
            lines = f.readlines()
        for line in lines:
            match = re.match(r'set PROJECT\((.*?)\) "(.*)"', line)
            if match:
                params[match.group(1)] = match.group(2)
        self.import_bspec_config_params(params)

    def export_bspec_project_file(self, filename):
        """Export project settings to a .bspec file.

        This does not export v_path."""
        with open(os.path.join(os.path.realpath(os.path.dirname(os.path.realpath(__file__))), 'templates', 'template.bspec')) as f:
            bspec_project_template = f.read()
        params = self.export_bspec_config_params()
        bspec_project_text = bspec_project_template.format(**params)
        with open(filename, 'w') as f:
            f.write(bspec_project_text)

    def import_bspec_config_params(self, params):
        """Imports project settings from parameters defined in a *.bspec file.

        This does not import v_path."""
        self.top_file = params['TOP_FILE']
        self.top_module = params['TOP_MODULE']
        self.bsv_path = list(tclstring_to_list(params['PATHS']))
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

        # strip default path arguments from self.bsv_path
        for path in BSVProject.default_paths:
            if path in self.bsv_path:
                self.bsv_path.remove(path)
        # assume the default v_path
        self.v_path = [ os.path.join( os.environ['BLUESPECDIR'], 'Verilog' ) ]

    def export_bspec_config_params(self):
        """Exports project settings to a dict of *.bspec file parameters.

        This does not export v_path."""
        params = {}
        params['TOP_FILE'] = self.top_file
        params['TOP_MODULE'] = self.top_module
        params['PATHS'] = list_to_tclstring([self.build_dir] + self.bsv_path + BSVProject.default_paths)
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

    def populate_packages_and_modules(self):
        """Populates self.packages and self.modules members using information from bluetcl.

        self.packages is a dictionary mapping package names to BluespecPackage objects.
        self.modules is a dictionary mapping module names to BluespecModule objects."""
        if self.packages is not None:
            raise Exception('packages already populated')
        if self.modules is not None:
            raise Exception('modules already populated')
        if not os.path.isfile(os.path.join(self.build_dir, self.top_module + '.ba')):
            raise Exception("top file not elaborated: either you forgot to build the design or the top module doesn't have a (* synthesize *) attribute")
        with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
            bluetcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            # load top package
            bluetcl.eval('Bluetcl::bpackage load %s' % os.path.basename(self.top_file).split('.')[0])
            # list all packages
            packages = bluetcl.eval('Bluetcl::bpackage list', to_list = True)

            self.packages = { pkg_name : BluespecPackage(pkg_name, bluetcl) for pkg_name in packages}
            self.modules = {}
            for package_name in self.packages:
                for module in self.packages[package_name].modules:
                    if module not in self.modules:
                        self.modules[module] = BluespecModule(module, bluetcl)

    # Advanced Functions
    #####################
    def get_submodules(self):
        """Returns a dictionary of submodules for each module in the current package.

        The dictionary has module names as keys and lists of (instance_name, module_name) tuples as values."""

        submodule_dict = {}
        with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
            bluetcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            bluetcl.eval('Bluetcl::bpackage load %s' % os.path.basename(self.top_file).split('.')[0])
            packages = bluetcl.eval('Bluetcl::bpackage list', to_list = True)

            # "Bluetcl::defs module <pkg>" returns modules with package names as well,
            # but "Bluetcl::module submods <mod>" doesn't accept package names, so they should be stripped
            modules = [mod.split('::')[-1] for pkg in packages for mod in bluetcl.eval('Bluetcl::defs module %s' % pkg, to_list = True)]
            uniq_modules = []
            for mod in modules:
                if mod not in uniq_modules:
                    uniq_modules.append(mod)
            for module in uniq_modules:
                bluetcl.eval('Bluetcl::module load %s' % module)
                user_or_prim, submodules, functions = tclstring_to_nested_list(bluetcl.eval('Bluetcl::module submods %s' % module))
                # If there is only one submodule, "Bluetcl::module submods <mod>" doesn't return a list of lists
                if isinstance(submodules, str):
                    if submodules == '':
                        submodules = tuple()
                    else:
                        submodules = (tuple(submodules.split(' ')),)
                if user_or_prim == 'user':
                    submodule_dict[module] = submodules
        return submodule_dict

    def get_rule_method_calls(self):
        """Returns a dictionary of rules and methodcalls for each rule in the current package.

        The dictionary contains a list of (rule, methods) tuples in execution order."""

        rule_method_call_dict = {}
        with tclwrapper.TCLWrapper('bluetcl') as bluetcl:
            bluetcl.eval('Bluetcl::flags set -verilog ' + ' '.join(self.get_path_arg()))
            bluetcl.eval('Bluetcl::bpackage load %s' % os.path.basename(self.top_file).split('.')[0])
            packages = bluetcl.eval('Bluetcl::bpackage list', to_list = True)

            # "Bluetcl::defs module <pkg>" returns modules with package names as well,
            # but "Bluetcl::module submods <mod>" doesn't accept package names, so they should be stripped
            modules = [mod.split('::')[-1] for pkg in packages for mod in bluetcl.eval('Bluetcl::defs module %s' % pkg, to_list = True)]
            uniq_modules = []
            for mod in modules:
                if mod not in uniq_modules:
                    uniq_modules.append(mod)
            for module in uniq_modules:
                bluetcl.eval('Bluetcl::module load %s' % module)
                execution_order = tclstring_to_list(bluetcl.eval('Bluetcl::schedule execution %s' % module))
                rule_method_call_dict[module] = []
                for rule in execution_order:
                    rule_info = tclstring_to_list(bluetcl.eval('Bluetcl::rule full %s %s' % (module, rule)))
                    # look for item that has 'methods' as its first element
                    # assume its always the 3rd element
                    if not rule_info[3].startswith('methods'):
                        raise Exception('method is expected to be the 3rd element from "Bluetcl::rule full <mod> <rule>"')
                    methods_tclstring = str(rule_info[3][len('methods '):])
                    method_calls = tclstring_to_flat_list(methods_tclstring)
                    rule_method_call_dict[module].append((rule, method_calls))
        return rule_method_call_dict

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

    def get_complete_schedule_from_bluesim(self):
        """Returns the complete schedule for the top module.

        The schedule is a combination of top-level interface methods, top-level
        rules, and submodule rules. This requires compiling for bluesim.
        """
        # The complete schedule can be inferred by this file
        bluesim_model_file = os.path.join(self.sim_dir, 'model_%s.cxx' % self.top_module)
        # bluesim compilation is required to generate the bluesim_model_file
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

    def get_complete_schedule(self, module_name = None):
        """Returns the complete schedule for the top module.

        The schedule is a combination of top-level interface methods, top-level
        rules, and submodule rules.
        """

        # from scratch
        if self.modules is None:
            self.populate_packages_and_modules()

        if module_name is None:
            module_name = self.top_module

        instance_dict = {}
        worklist = [ (module_name, self.modules[module_name]) ]
        while len(worklist) != 0:
            instance_name, module = worklist.pop()
            instance_dict[instance_name] = module
            for submodule_instance, submodule_type in module.submodules:
                if submodule_type in self.modules:
                    worklist.append((instance_name + '.' + submodule_instance, self.modules[submodule_type]))

        partial_order = {}
        called_methods = {} # list of rules (and methods) that call a given method
        for instance_name, module in instance_dict.items():
            # add execution to partial order
            for i in range(len(module.execution)):
                partial_order[instance_name + '.' + module.execution[i]] = [instance_name + '.' + x for x in module.execution[i+1:]]
            # add method calls to partial order
            # get list of rules that call each method
            for rule, methods in module.method_calls_by_rule.items():
                full_rule_name = instance_name + '.' + rule
                for method in methods:
                    full_method_name = instance_name + '.' + method
                    if full_method_name not in called_methods:
                        called_methods[full_method_name] = [full_rule_name]
                    else:
                        called_methods[full_method_name].append(full_rule_name)
            # make sure all lower-level methods appear in called_methods, even if they are not called by a rule
            for rule in module.execution:
                if rule.count('.') > 1 and not rule.split('.')[-1].startswith('RL_'):
                    # this is a lower-level method
                    if rule not in called_methods:
                        called_methods[rule] = []
        # the items in called_methods are a list of rules and methods, this function helps to get just rules
        # similar to taking the transitive closure of called_methods
        def get_rules_from_rule_or_method(x):
            if x not in called_methods:
                # x is a rule or top-level method
                return [x]
            rules = [get_rules_from_rule_or_method(y) for y in called_methods[x]]
            rules = sum(rules, []) # flatten rules
            return list(set(rules))
        # create a new partial order that doesn't contain called methods
        new_partial_order = {}
        for first_rule, second_rules in partial_order.items():
            actual_first_rules = get_rules_from_rule_or_method(first_rule)

            actual_second_rules = []
            for second_rule in second_rules:
                actual_second_rules += get_rules_from_rule_or_method(second_rule)

            for r1 in actual_first_rules:
                if r1 not in new_partial_order:
                    new_partial_order[r1] = actual_second_rules
                else:
                    new_partial_order[r1] += actual_second_rules
        # cleanup new_partial_order
        for first_rule in new_partial_order:
            new_partial_order[first_rule] = list(set(new_partial_order[first_rule]))
            while new_partial_order[first_rule].count(first_rule) > 0:
                new_partial_order[first_rule].remove(first_rule)
        partial_order = new_partial_order.copy()

        full_schedule = []
        to_schedule = set(partial_order.keys())
        # schedule rules from end to beginning
        while len(to_schedule) > 0:
            removed_candidate = False
            for candidate in to_schedule:
                if len(partial_order[candidate]) == 0:
                    to_schedule.remove(candidate)
                    full_schedule = [candidate] + full_schedule
                    # remove candidate from all the partial orders
                    for x in partial_order:
                        while partial_order[x].count(candidate) > 0:
                            partial_order[x].remove(candidate)
                    removed_candidate = True
                    break
            if not removed_candidate:
                raise Exception("getting the full schedule failed")

        return full_schedule

# There are no links between bluespec packages and modules, everything is done by name
class BluespecPackage:
    def __init__(self, name, bluetcl):
        # first open package if its not already open
        bluetcl.eval('Bluetcl::bpackage load %s' % name)
        self.name = name
        def remove_package_name(n):
            return n.split('::')[-1]
        self.types = list(map(remove_package_name, tclstring_to_list(bluetcl.eval('Bluetcl::defs type %s' % name))))
        self.modules = list(map(remove_package_name, tclstring_to_list(bluetcl.eval('Bluetcl::defs module %s' % name))))
        self.func = list(map(remove_package_name, tclstring_to_list(bluetcl.eval('Bluetcl::defs func %s' % name))))

class BluespecModule:
    def __init__(self, name, bluetcl):
        if '::' in name:
            self.package = name.split('::')[0]
            self.name = name.split('::')[1]
        else:
            self.package = None
            self.name = name
        bluetcl.eval('Bluetcl::module load %s' % self.name)

        # get scheduling info (urgency and execution)
        urgency_tclstrings = tclstring_to_list(bluetcl.eval('Bluetcl::schedule urgency %s' % self.name))
        urgency_lists = list(map(tclstring_to_flat_list, urgency_tclstrings))
        # urgency is a list of rules that block a given rule
        self.urgency = { x[0] : x[1:] for x in urgency_lists}
        self.execution = tclstring_to_list(bluetcl.eval('Bluetcl::schedule execution %s' % self.name))
        self.methodinfo = tclstring_to_list(bluetcl.eval('Bluetcl::schedule methodinfo %s' % self.name))
        self.pathinfo = tclstring_to_list(bluetcl.eval('Bluetcl::schedule pathinfo %s' % self.name))

        # get submodule info (list of submodule instance names and constructors)
        user_or_prim, submodules, functions = tclstring_to_nested_list(bluetcl.eval('Bluetcl::module submods %s' % self.name))
        if len(functions) != 0:
            print('There is a function used in %s' % self.name)
        # If there is only one submodule, "Bluetcl::module submods <mod>" doesn't return a list of lists
        if isinstance(submodules, str):
            if submodules == '':
                submodules = tuple()
            else:
                submodules = (tuple(submodules.split()),)
        if user_or_prim == 'user':
            self.submodules = submodules
        else:
            self.submodules = tuple()

        # get rule info (methods called by each rule)
        self.method_calls_by_rule = {}
        for rule in self.execution:
            rule_info = tclstring_to_list(bluetcl.eval('Bluetcl::rule full %s %s' % (self.name, rule)))
            # look for item that has 'methods' as its first element
            # It is usually the 3rd element, but if a rule has attributes, then it is the 4th element
            methods_tclstring = None
            for i in range(len(rule_info)):
                if rule_info[i].startswith('methods'):
                    methods_tclstring = str(rule_info[i][len('methods '):])
            if methods_tclstring is None:
                raise Exception('"method" tag was not found in "Bluetcl::rule full <mod> <rule>"')
            method_calls = tclstring_to_flat_list(methods_tclstring)
            self.method_calls_by_rule[rule] = method_calls

        # sanity check
        conflict = False
        for i in range(len(self.execution)):
            rule = self.execution[i]
            conflicting_rules = self.urgency[rule]
            for conflicting_rule in conflicting_rules:
                if conflicting_rule not in self.execution[:i]:
                    # I'm not sure why this happens sometimes, but I'm just allowing it for now
                    # raise Exception("a rule is blocked by a rule that is later in execution order")
                    conflict = True
        if conflict:
            print('module {} has an urgency and conflicts with the execution order'.format(self.name))
