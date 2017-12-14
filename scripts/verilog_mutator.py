#!/usr/bin/env python3

import io
import os
from pyverilog.vparser.parser import parse
import pyverilog.vparser.ast as ast
from pyverilog.ast_code_generator.codegen import ASTCodeGenerator, ConvertVisitor

class MyVisitor(ConvertVisitor):
    def __init__(self):
        self.decls = []
    def visit_Decl(self, node):
        decls = decls ++ node.list
        # do something

class CustomizedASTCodeGenerator(ASTCodeGenerator):
    '''Same as ASTCodeGenerator except for adding newlines between signal
    declarations that came from the same source declaration statement.'''
    def __init__(self, indentsize = 2):
        ASTCodeGenerator.__init__(self, indentsize)
    def visit_Decl(self, node):
        '''Adds newline between declarations if multiple signals were declared together'''
        return '\n'.join([self.visit(item) for item in node.list])

class VerilogMutator:
    def __init__(self, verilog_filename):
        try:
            with open(verilog_filename) as f:
                pass
        except:
            raise ValueError(verilog_filename + ' does not exist')
        self.ast_root, self.directives = parse([verilog_filename], preprocess_include = [], preprocess_define = [])
        self.codegen = CustomizedASTCodeGenerator()
        definitions = self.ast_root.description.definitions
        self.module = None
        for definition in definitions:
            if isinstance(definition, ast.ModuleDef):
                if self.module is None:
                    self.module = definition
                else:
                    raise ValueError(verilog_filename + ' has more than one module defined within it')
        if self.module is None:
            raise ValueError(verilog_filename + ' has no module defined within it')
        # self.module has name, paramlist, portlist, and items

    def get_ast(self):
        stringio = io.StringIO()
        self.ast_root.show(buf = stringio)
        stringio.seek(0)
        ast = stringio.read()
        stringio.close()
        return ast

    def get_verilog(self):
        '''Formats the modified verilog ast as verilog source stored in a str'''
        return self.codegen.visit(self.ast_root)

    def write_verilog(self, output_verilog_filename):
        '''Writes the modified verilog to the specified file'''
        with open(output_verilog_filename, 'w') as f:
            f.write( self.get_verilog() )

    def get_nodes_by_type(self, node_type, search_root_node = None, nested = True):
        '''Constructs a list of AST nodes of a given type'''
        if search_root_node == None:
            search_root_node = self.ast_root
        if isinstance(search_root_node, node_type):
            if not nested:
                return [search_root_node]
            else:
                return sum(list(map(lambda x: self.get_nodes_by_type(node_type, x, nested), search_root_node.children())), [search_root_node])
        else:
            return sum(list(map(lambda x: self.get_nodes_by_type(node_type, x, nested), search_root_node.children())), [])

    def get_instance(self, name):
        instances = self.get_nodes_by_type(ast.Instance)
        for instance in instances:
            if instance.name == name:
                return instance
        return None

    def get_decl_names(self, node_type = None):
        decls = self.get_nodes_by_type(ast.Decl)
        names = []
        for decl in decls:
            for item in decl.list:
                if node_type is None or isinstance(item, node_type):
                    names.append(item.name)
        return names

    def add_decls(self, names, node_type, width = None):
        if not issubclass(node_type, ast.Variable):
            print('ERROR: invalid argument for node_type in VerilogMutator.add_decls()')
        # preprocessing inputs if they don't match the expected type
        if isinstance(names, str):
            names = [names]
        if isinstance(width, int):
            if width == 1:
                width = None
            else:
                width = ast.Width(ast.IntConst(width - 1), ast.IntConst(0)) # msb, lsb
        # collect all the declared signals
        new_decls = []
        for name in names:
            new_decls.append(node_type(name, width))
        # wrap them in a Decl node
        decl = ast.Decl(new_decls)
        # find index to insert at
        insert_index = 0
        for i in range(len(self.module.items)):
            if isinstance(self.module.items[i], ast.Decl):
                insert_index = i + 1
        # insert the new Decl node
        self.module.items = self.module.items[:insert_index] + (decl,) + self.module.items[insert_index:]

    def get_assigns(self):
        return [item for item in self.module.items if isinstance(item, ast.Assign)]

    def get_assign(self, name):
        # look through items in module for assignment matching requested name
        for item in self.module.items:
            if isinstance(item, ast.Assign) and isinstance(item.left.var, ast.Identifier) and item.left.var.name == name:
                return item
        raise ValueError('No assignment found for ' + name)

    def add_assign(self, lhs, rhs):
        assign = ast.Assign(ast.Lvalue(ast.Identifier(lhs)), ast.Rvalue(rhs))
        # find index to insert at
        insert_index = 0
        for i in range(len(self.module.items)):
            if isinstance(self.module.items[i], ast.Assign):
                insert_index = i + 1
        # insert the new assign node
        self.module.items = self.module.items[:insert_index] + (assign,) + self.module.items[insert_index:]

    def add_ports(self, names):
        if isinstance(names, str):
            name = [names]
        new_ports = []
        for name in names:
            new_ports.append(ast.Port(name, None, None))
        self.module.portlist.ports = self.module.portlist.ports + tuple(new_ports)

    def get_rules_in_scheduling_order(self):
        # get names of rules by looking for declared signals starting with the prefix
        # 'CAN_FIRE_RL_'. This will produce the rule names in scheduling order since
        # the bluespec scheduler declares CAN_FIRE signals in scheduling order.
        names = self.get_decl_names()
        prefix = 'CAN_FIRE_RL_'
        rule_names = [name[len(prefix):] for name in names if name.startswith(prefix)]
        return rule_names

    def get_submodules(self):
        instances = self.get_nodes_by_type(ast.Instance)
        # instance name, module name
        return [(instance.name, instance.module) for instance in instances]

    def expose_internal_scheduling_signals(self, rule_names = None):
        if rule_names is None:
            rule_names = self.get_rules_in_scheduling_order()
        # new ports
        self.add_ports(['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'])

        # new declarations
        # declare new ports as inputs or outputs
        self.add_decls(['CAN_FIRE', 'WILL_FIRE'], ast.Output, width = len(rule_names))
        self.add_decls(['FORCE_FIRE', 'BLOCK_FIRE'], ast.Input, width = len(rule_names))

        # declare individual BLOCK_FIRE_RL_* and FORCE_FIRE_RL_* signals for each rule
        for name in rule_names:
            self.add_decls('BLOCK_FIRE_RL_' + name, ast.Wire)
            self.add_decls('FORCE_FIRE_RL_' + name, ast.Wire)

        # new assigns
        # assign CAN_FIRE and WILL_FIRE as the concatenation of individually named signals
        can_fires = []
        will_fires = []
        for name in rule_names:
            can_fires.append(ast.Identifier('CAN_FIRE_RL_' + name))
            will_fires.append(ast.Identifier('WILL_FIRE_RL_' + name))
        # reverse arrays of signals to get first signal in bit 0 of the concatenation
        can_fires.reverse()
        will_fires.reverse()
        self.add_assign('CAN_FIRE', ast.Concat(can_fires))
        self.add_assign('WILL_FIRE', ast.Concat(will_fires))

        # split BLOCK_FIRE and FORCE_FIRE into individually named signals
        for i in range(len(rule_names)):
            name = rule_names[i]
            self.add_assign('BLOCK_FIRE_RL_' + name, ast.Partselect(ast.Identifier('BLOCK_FIRE'), ast.IntConst(i), ast.IntConst(i)))
            self.add_assign('FORCE_FIRE_RL_' + name, ast.Partselect(ast.Identifier('FORCE_FIRE'), ast.IntConst(i), ast.IntConst(i)))

        # updating old assignments of WILL_FIRE_RL_*
        for rule in rule_names:
            assign = self.get_assign('WILL_FIRE_RL_' + rule)
            new_rhs = ast.Or(ast.Identifier('FORCE_FIRE_RL_' + rule), ast.And(ast.Unot(ast.Identifier('BLOCK_FIRE_RL_' + rule)), assign.right.var))
            assign.right.var = new_rhs

    def expose_internal_scheduling_signals_hierarchically(self, num_rules_per_module, rule_names = None):
        if rule_names is None:
            rule_names = self.get_rules_in_scheduling_order()
        # new ports
        self.add_ports(['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'])

        # collect all the CAN_FIRE and WILL_FIRE signals for future concatenation
        can_fires = []
        will_fires = []
        for name in rule_names:
            can_fires.append(ast.Identifier('CAN_FIRE_RL_' + name))
            will_fires.append(ast.Identifier('WILL_FIRE_RL_' + name))

        # instrument submodules
        top_signal_width = len(rule_names)
        instances = self.get_nodes_by_type(ast.Instance)
        for instance in instances:
            if instance.module in num_rules_per_module:
                if num_rules_per_module[instance.module] != 0:
                    num_submodule_rules = num_rules_per_module[instance.module]
                    # add ports to submodule
                    lsb = top_signal_width
                    msb = top_signal_width + num_submodule_rules - 1
                    top_signal_width += num_submodule_rules
                    new_ports = []
                    for name in ['CAN_FIRE', 'WILL_FIRE']:
                        # outputs
                        self.add_decls(name + '_MODULE_' + instance.name, ast.Wire, width = num_submodule_rules)
                        new_ports.append(ast.PortArg(name, ast.Identifier(name + '_MODULE_' + instance.name)))
                    for name in ['BLOCK_FIRE', 'FORCE_FIRE']:
                        # inputs
                        self.add_decls(name + '_MODULE_' + instance.name, ast.Wire, width = num_submodule_rules)
                        self.add_assign(name + '_MODULE_' + instance.name, ast.Partselect(ast.Identifier(name), ast.IntConst(msb), ast.IntConst(lsb)))
                        new_ports.append(ast.PortArg(name, ast.Identifier(name + '_MODULE_' + instance.name)))
                    instance.portlist = instance.portlist + tuple(new_ports)
                    # keep track of the modules CAN_FIRE and WILL_FIRE signals for future concatenation
                    can_fires.append(ast.Identifier('CAN_FIRE_MODULE_' + instance.name))
                    will_fires.append(ast.Identifier('WILL_FIRE_MODULE_' + instance.name))

        # new declarations
        # declare new ports as inputs or outputs
        self.add_decls(['CAN_FIRE', 'WILL_FIRE'], ast.Output, width = top_signal_width)
        self.add_decls(['FORCE_FIRE', 'BLOCK_FIRE'], ast.Input, width = top_signal_width)

        # declare individual BLOCK_FIRE_RL_* and FORCE_FIRE_RL_* signals for each rule
        for name in rule_names:
            self.add_decls('BLOCK_FIRE_RL_' + name, ast.Wire)
            self.add_decls('FORCE_FIRE_RL_' + name, ast.Wire)

        # new assigns
        # assign CAN_FIRE and WILL_FIRE as the concatenation of individually named signals
        # reverse arrays of signals to get first signal in bit 0 of the concatenation
        can_fires.reverse()
        will_fires.reverse()
        self.add_assign('CAN_FIRE', ast.Concat(can_fires))
        self.add_assign('WILL_FIRE', ast.Concat(will_fires))

        # split BLOCK_FIRE and FORCE_FIRE into individually named signals
        for i in range(len(rule_names)):
            name = rule_names[i]
            self.add_assign('BLOCK_FIRE_RL_' + name, ast.Partselect(ast.Identifier('BLOCK_FIRE'), ast.IntConst(i), ast.IntConst(i)))
            self.add_assign('FORCE_FIRE_RL_' + name, ast.Partselect(ast.Identifier('FORCE_FIRE'), ast.IntConst(i), ast.IntConst(i)))

        # updating old assignments of WILL_FIRE_RL_*
        for rule in rule_names:
            assign = self.get_assign('WILL_FIRE_RL_' + rule)
            new_rhs = ast.Or(ast.Identifier('FORCE_FIRE_RL_' + rule), ast.And(ast.Unot(ast.Identifier('BLOCK_FIRE_RL_' + rule)), assign.right.var))
            assign.right.var = new_rhs

    def expose_internal_scheduling_signals_hierarchically_alt(self, num_rules_per_module, scheduling_order = None):
        # if schedule isn't provided, assume rules first then modules
        if scheduling_order is None:
            scheduling_order = ['RL_' + x for x in self.get_rules_in_scheduling_order()] + ['MODULE_' + x for x, y in self.get_submodules()]
            print('Scheduling Order:\n    ' + '\n    '.join(scheduling_order))
        instance_to_module = {x: y for x, y in self.get_submodules()}
        can_fires = []
        will_fires = []
        total_num_bits = 0
        for name in scheduling_order:
            if name.startswith('RL_'):
                self.add_decls('BLOCK_FIRE_' + name, ast.Wire)
                self.add_decls('FORCE_FIRE_' + name, ast.Wire)
                # definition of BLOCK_FIRE and FORCE_FILE
                assign = self.get_assign('WILL_FIRE_' + name)
                new_rhs = ast.Or(ast.Identifier('FORCE_FIRE_' + name), ast.And(ast.Unot(ast.Identifier('BLOCK_FIRE_' + name)), assign.right.var))
                assign.right.var = new_rhs
                # definition of BLOCK_FIRE_* and FORCE_FIRE_* signals from top-level BLOCK_FIRE and FORCE_FIRE
                bit_index = total_num_bits
                total_num_bits += 1
                self.add_assign('BLOCK_FIRE_' + name, ast.Partselect(ast.Identifier('BLOCK_FIRE'), ast.IntConst(bit_index), ast.IntConst(bit_index)))
                self.add_assign('FORCE_FIRE_' + name, ast.Partselect(ast.Identifier('FORCE_FIRE'), ast.IntConst(bit_index), ast.IntConst(bit_index)))
                can_fires.append(ast.Identifier('CAN_FIRE_' + name))
                will_fires.append(ast.Identifier('WILL_FIRE_' + name))
            elif name.startswith('MODULE_'):
                instance_name = name[len('MODULE_'):]
                instance = self.get_instance(instance_name)
                module_name = instance_to_module[instance_name]
                if module_name not in num_rules_per_module:
                    continue
                num_submodule_rules = num_rules_per_module[module_name]
                if num_submodule_rules == 0:
                    continue
                for signal_type in ['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE']:
                    # declarations of all FIRE signals for the submodule
                    self.add_decls(signal_type + '_' + name, ast.Wire, width = num_submodule_rules)
                    # connection of all FIRE signals to the submodule
                    instance.portlist += (ast.PortArg(name, ast.Identifier(signal_type + '_' + name)),)
                # assignments of BLOCK_FIRE_* and FORCE_FIRE_* signals from top-level BLOCK_FIRE and FORCE_FIRE
                lsb = total_num_bits
                msb = total_num_bits + num_submodule_rules - 1
                total_num_bits += num_submodule_rules
                self.add_assign('BLOCK_FIRE_' + name, ast.Partselect(ast.Identifier('BLOCK_FIRE'), ast.IntConst(msb), ast.IntConst(lsb)))
                self.add_assign('FORCE_FIRE_' + name, ast.Partselect(ast.Identifier('FORCE_FIRE'), ast.IntConst(msb), ast.IntConst(lsb)))
                can_fires.append(ast.Identifier('CAN_FIRE_' + name))
                will_fires.append(ast.Identifier('WILL_FIRE_' + name))
            elif name.startswith('METH_'):
                raise ValueError('"METH_" scheduling signals are not supported yet')
            else:
                raise ValueError('unexpected entry "%s" in scheduling_order' % name)

        # new ports
        self.add_ports(['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'])
        # connect CAN_FIRE and WILL_FIRE
        can_fires.reverse()
        will_fires.reverse()
        self.add_assign('CAN_FIRE', ast.Concat(can_fires))
        self.add_assign('WILL_FIRE', ast.Concat(will_fires))

class VerilogProject:
    def __init__(self, top_module, verilog_path):
        # read through verilog files and build hierarchy
        # this assumes a module named mkModule is found in a file called mkModule.v
        self.top = top_module
        # module_name -> (VerilogMutator or None)
        self.modules = {}
        # module_name -> [(instance_name, module_name)]
        self.module_hierarchy = {}
        # set of modules which have been instrumented already
        self.instrumented_modules = []
        # now populate self.modules
        modules_to_parse = [self.top]
        while len(modules_to_parse) != 0:
            module = modules_to_parse[0]
            modules_to_parse = modules_to_parse[1:]
            filename = verilog_path + '/' + module + '.v'
            try:
                self.modules[module] = VerilogMutator(filename)
                submodules = self.modules[module].get_submodules()
                self.module_hierarchy[module] = submodules
                for instance_name, submodule_name in submodules:
                    if submodule_name not in self.modules and submodule_name not in modules_to_parse:
                        modules_to_parse.append(submodule_name)
            except Exception as e:
                self.modules[module] = None
                #print('WARNING: unable to step through submodule "%s"' % module)
                #print(str(e))

    def get_hierarchy(self, module_name = None, depth = 0):
        ret = ''
        if module_name is None:
            ret += ('  ' * depth) + self.top + '\n'
            ret += self.get_hierarchy(self.top, 1)
        elif module_name in self.module_hierarchy:
            for instance_name, module_name in self.module_hierarchy[module_name]:
                ret += ('  ' * depth) + instance_name + ' (' + module_name + ')' + '\n'
                ret += self.get_hierarchy(module_name, depth + 1)
        return ret

    def expose_fire_signals_hierarchically(self):
        num_rules_per_module = {}
        for module_name in self.modules:
            if self.modules[module_name] is None:
                num_rules_per_module[module_name] = 0
            else:
                num_rules_per_module[module_name] = len(self.modules[module_name].get_rules_in_scheduling_order())
        for module_name in self.modules:
            if self.modules[module_name] is not None:
                self.modules[module_name].expose_internal_scheduling_signals_hierarchically_alt(num_rules_per_module)

    def write_verilog(self, directory):
        for module_name in self.modules:
            if self.modules[module_name] is not None:
                with open(directory + '/' + module_name + '.v', 'w') as f:
                    f.write(self.modules[module_name].get_verilog())

if __name__ == '__main__':
    import sys
    verilog_path_and_filename = sys.argv[1]
    if verilog_path_and_filename[-2:] != '.v':
        raise ValueError('Input filename should end in ".v"')
    verilog_path = os.path.dirname(os.path.realpath(verilog_path_and_filename))
    verilog_filename = os.path.basename(os.path.realpath(verilog_path_and_filename))
    verilog_project = VerilogProject(verilog_filename[:-2], verilog_path)
    mutator = verilog_project.modules[verilog_project.top]

    out_path = 'out'
    try:
        os.mkdir(out_path)
    except FileExistsError:
        pass

    with open(out_path + '/' + verilog_filename[:-2] + '_ast.txt', 'w') as f:
        f.write(mutator.get_ast())
    with open(out_path + '/' + verilog_filename[:-2] + '_hierarchy.txt', 'w') as f:
        f.write(verilog_project.get_hierarchy())
    with open(out_path + '/' + verilog_filename[:-2] + '_passthrough.v', 'w') as f:
        f.write(mutator.get_verilog())

    rule_names = mutator.get_rules_in_scheduling_order()

    with open(out_path + '/' + verilog_filename[:-2] + '_rules.txt', 'w') as f:
        f.write('\n'.join(rule_names) + '\n')

    verilog_project.expose_fire_signals_hierarchically()

    verilog_project.write_verilog(out_path)
