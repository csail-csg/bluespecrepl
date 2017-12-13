#!/usr/bin/env python3

import io
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
        names = mutator.get_decl_names()
        prefix = 'CAN_FIRE_RL_'
        rule_names = [name[len(prefix):] for name in names if name.startswith(prefix)]
        return rule_names

    def expose_internal_scheduling_signals(self, rule_names = None):
        if rule_names is None:
            rule_names = self.get_rules_in_scheduling_order()
        # new ports
        mutator.add_ports(['CAN_FIRE', 'WILL_FIRE', 'BLOCK_FIRE', 'FORCE_FIRE'])

        # new declarations
        # declare new ports as inputs or outputs
        mutator.add_decls(['CAN_FIRE', 'WILL_FIRE'], ast.Output, width = len(rule_names))
        mutator.add_decls(['FORCE_FIRE', 'BLOCK_FIRE'], ast.Input, width = len(rule_names))

        # declare individual BLOCK_FIRE_RL_* and FORCE_FIRE_RL_* signals for each rule
        for name in rule_names:
            mutator.add_decls('BLOCK_FIRE_RL_' + name, ast.Wire)
            mutator.add_decls('FORCE_FIRE_RL_' + name, ast.Wire)

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
        mutator.add_assign('CAN_FIRE', ast.Concat(can_fires))
        mutator.add_assign('WILL_FIRE', ast.Concat(will_fires))

        # split BLOCK_FIRE and FORCE_FIRE into individually named signals
        for i in range(len(rule_names)):
            name = rule_names[i]
            mutator.add_assign('BLOCK_FIRE_RL_' + name, ast.Partselect(ast.Identifier('BLOCK_FIRE'), ast.IntConst(i), ast.IntConst(i)))
            mutator.add_assign('FORCE_FIRE_RL_' + name, ast.Partselect(ast.Identifier('FORCE_FIRE'), ast.IntConst(i), ast.IntConst(i)))

        # updating old assignments of WILL_FIRE_RL_*
        for rule in rule_names:
            assign = mutator.get_assign('WILL_FIRE_RL_' + rule)
            new_rhs = ast.Or(ast.Identifier('FORCE_FIRE_RL_' + rule), ast.And(ast.Unot(ast.Identifier('BLOCK_FIRE_RL_' + rule)), assign.right.var))
            assign.right.var = new_rhs

if __name__ == '__main__':
    import sys
    verilog_filename = sys.argv[1]
    if verilog_filename[-2:] != '.v':
        raise ValueError('Input filename should end in ".v"')

    mutator = VerilogMutator(verilog_filename)

    with open(verilog_filename[:-2] + '_ast.txt', 'w') as f:
        f.write(mutator.get_ast())
    with open(verilog_filename[:-2] + '_passthrough.v', 'w') as f:
        f.write(mutator.get_verilog())

    rule_names = mutator.get_rules_in_scheduling_order()

    with open(verilog_filename[:-2] + '_rules.txt', 'w') as f:
        f.write('\n'.join(rule_names) + '\n')

    mutator.expose_internal_scheduling_signals(rule_names = rule_names)

    with open(verilog_filename[:-2] + '_instrumented.v', 'w') as f:
        f.write(mutator.get_verilog())
