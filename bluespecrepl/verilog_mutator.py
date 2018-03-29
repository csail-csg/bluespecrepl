#!/usr/bin/env python3

import io
import os
from pyverilog.vparser.parser import parse
import pyverilog.vparser.ast as ast
from pyverilog.ast_code_generator.codegen import ASTCodeGenerator, ConvertVisitor
import jinja2

class CustomizedASTCodeGenerator(ASTCodeGenerator):
    '''Same as ASTCodeGenerator except for adding newlines between signal
    declarations that came from the same source declaration statement.'''
    def __init__(self, indentsize = 2):
        ASTCodeGenerator.__init__(self, indentsize)
    def visit_Decl(self, node):
        '''Adds newline between declarations if multiple signals were declared together'''
        return '\n'.join([self.visit(item) for item in node.list])

class VerilogMutator:
    def __init__(self, verilog_file_path):
        if not os.path.isfile(verilog_file_path):
            raise ValueError(verilog_file_path + ' is not a valid file')
        self.ast_root, self.directives = parse([verilog_file_path], preprocess_include = [], preprocess_define = [])
        self.codegen = CustomizedASTCodeGenerator()
        definitions = self.ast_root.description.definitions
        self.module = None
        for definition in definitions:
            if isinstance(definition, ast.ModuleDef):
                if self.module is None:
                    self.module = definition
                else:
                    raise ValueError(verilog_file_path + ' has more than one module defined within it')
        if self.module is None:
            raise ValueError(verilog_file_path + ' has no module defined within it')
        # self.module has name, paramlist, portlist, and items

    def get_ast(self):
        '''Get the abstract syntax tree in a human-readable text format'''
        stringio = io.StringIO()
        self.ast_root.show(buf = stringio)
        stringio.seek(0)
        ast = stringio.read()
        stringio.close()
        return ast

    def get_verilog(self):
        '''Formats the modified verilog AST as verilog source stored in a str'''
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
        '''Gets AST nodes for module instances by name'''
        instances = self.get_nodes_by_type(ast.Instance)
        for instance in instances:
            if instance.name == name:
                return instance
        return None

    def get_decl_names(self, node_type = None):
        '''Gets names of declared signals (restricted to a specific type if node_type is provided)'''
        decls = self.get_nodes_by_type(ast.Decl)
        names = []
        for decl in decls:
            for item in decl.list:
                if node_type is None or isinstance(item, node_type):
                    names.append(item.name)
        return names

    def add_decls(self, names, node_type, width = None):
        '''Adds new signal declarations'''
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
        '''Gets AST node for each assignment'''
        return [item for item in self.module.items if isinstance(item, ast.Assign)]

    def get_assign(self, name):
        '''Get assignment for a specific signal'''
        # look through items in module for assignment matching requested name
        for item in self.module.items:
            if isinstance(item, ast.Assign) and isinstance(item.left.var, ast.Identifier) and item.left.var.name == name:
                return item
        raise ValueError('No assignment found for ' + name)

    def add_assign(self, lhs, rhs):
        '''Adds a new assignment'''
        assign = ast.Assign(ast.Lvalue(ast.Identifier(lhs)), ast.Rvalue(rhs))
        # find index to insert at
        insert_index = 0
        for i in range(len(self.module.items)):
            if isinstance(self.module.items[i], ast.Assign):
                insert_index = i + 1
        # insert the new assign node
        self.module.items = self.module.items[:insert_index] + (assign,) + self.module.items[insert_index:]

    def add_ports(self, names):
        '''Adds new ports to the end of the module's ports'''
        if isinstance(names, str):
            name = [names]
        new_ports = []
        for name in names:
            new_ports.append(ast.Port(name, None, None))
        self.module.portlist.ports = self.module.portlist.ports + tuple(new_ports)

    def get_inputs(self):
        """Returns list of tuples of input name and width."""
        inputs = []
        decls = self.get_nodes_by_type(ast.Decl)
        for decl in decls:
            for item in decl.list:
                if isinstance(item, ast.Input):
                    if item.width is None:
                        inputs.append((item.name, 1))
                    else:
                        # TODO: This line doesn't work if either of the bounds is not just a number (e.g. msb = 7-1)
                        inputs.append((item.name, int(item.width.msb.value) - int(item.width.lsb.value) + 1))
        return inputs

    def get_outputs(self):
        """Returns list of tuples of output name and width."""
        outputs = []
        decls = self.get_nodes_by_type(ast.Decl)
        for decl in decls:
            for item in decl.list:
                if isinstance(item, ast.Output):
                    if item.width is None:
                        outputs.append((item.name, 1))
                    else:
                        # TODO: This line doesn't work if either of the bounds is not just a number (e.g. msb = 7-1)
                        outputs.append((item.name, int(item.width.msb.value) - int(item.width.lsb.value) + 1))
        return outputs

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

    def get_default_scheduling_order(self):
        # if schedule isn't provided, assume rules first then modules
        scheduling_order = ['RL_' + x for x in self.get_rules_in_scheduling_order()] + ['MODULE_' + x for x, y in self.get_submodules()]
        return scheduling_order

    def expose_internal_scheduling_signals(self, num_rules_per_module = None, scheduling_order = None):
        # if schedule isn't provided, assume rules first then modules
        if scheduling_order is None:
            scheduling_order = ['RL_' + x for x in self.get_rules_in_scheduling_order()] + ['MODULE_' + x for x, y in self.get_submodules()]
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
                if num_rules_per_module is None:
                    continue
                if module_name not in num_rules_per_module:
                    continue
                num_submodule_rules = num_rules_per_module[module_name]
                if num_submodule_rules == 0:
                    continue
                for signal_type in ['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE']:
                    # declarations of all FIRE signals for the submodule
                    self.add_decls(signal_type + '_' + name, ast.Wire, width = num_submodule_rules)
                    # connection of all FIRE signals to the submodule
                    instance.portlist += (ast.PortArg(signal_type, ast.Identifier(signal_type + '_' + name)),)
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

        if total_num_bits != 0:
            # new ports
            self.add_ports(['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'])
            self.add_decls('CAN_FIRE', ast.Output, width = total_num_bits)
            self.add_decls('WILL_FIRE', ast.Output, width = total_num_bits)
            self.add_decls('BLOCK_FIRE', ast.Input, width = total_num_bits)
            self.add_decls('FORCE_FIRE', ast.Input, width = total_num_bits)
            self.add_decls('CAN_FIRE', ast.Wire, width = total_num_bits)
            self.add_decls('WILL_FIRE', ast.Wire, width = total_num_bits)
            # connect CAN_FIRE and WILL_FIRE
            can_fires.reverse()
            will_fires.reverse()
            self.add_assign('CAN_FIRE', ast.Concat(can_fires))
            self.add_assign('WILL_FIRE', ast.Concat(will_fires))

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

    with open(out_path + '/' + verilog_filename[:-2] + '_wrapper.cpp', 'w') as f:
        f.write(verilog_project.generate_verilator_cpp_wrapper())
