#!/usr/bin/env python3

import tclwrapper

# Note: To get more information about bluetcl, run the command "Bluetcl::help" within bluetcl

class Virtual:
    # { class : { field : is_array }}
    object_fields = {
        'VInst' :
            {'kind' : False,
            'name' : False,
            'name bsv' : False,
            'name synth' : False,
            'path' : False,
            'path bsv' : False,
            'path synth' : False,
            'signals' : True,
            'parent' : False,
            'children' : False,
            'ancestors' : True,
            'position' : False,
            'predsignals' : True,
            'bodysignals' : True,
            'predmethods' : True,
            'bodymethods' : True,
            'interface' : True,
            'portmethods' : True,
            'class' : False},
        'VMethod' :
            {'inst' : False,
            'name' : False,
            'position' : False,
            'path' : False,
            'path bsv' : False,
            'path synth' : False,
            'signals' : True,
            'class' : False},
        'VSignal' :
            {'kind' : False,
            'name' : False,
            'path' : False,
            'path bsv' : False,
            'path synth' : False,
            'type' : False,
            'inst' : False,
            'position' : False,
            'class' : False}}
            
    def __init__(self, bluetcl):
        self.objects = {}
        self.bluetcl = bluetcl
        self.bluetcl.eval('package require Virtual')
        self.top = self.bluetcl.eval('Virtual::inst top')
        self.insts = self.bluetcl.eval('Virtual::inst filter *', to_list = True)
        print('self.insts = ' + str(self.insts))
        self.signals = self.bluetcl.eval('Virtual::signal filter *', to_list = True)
        for inst in self.insts:
            self.populate_object(inst)
        for signal in self.signals:
            self.populate_object(signal)
        # now get all the methods
        self.methods = []
        # fields where methods are found
        method_fields = ['predmethods', 'bodymethods', 'portmethods']
        for _, fields in self.objects.items():
            for method_field in method_fields:
                if method_field in fields:
                    for method in fields[method_field]:
                        if method not in self.methods:
                            self.methods.append(method)
        self.methods.sort()
        for method in self.methods:
            self.populate_object(method)

    def get_field(self, obj, field, is_list = False):
        return self.bluetcl.eval('%s %s' % (obj, field), to_list = is_list)

    def populate_object(self, obj):
        obj_class = self.get_field(obj, 'class')
        fields = {}
        field_specs = Virtual.object_fields[obj_class]
        for field, is_array in field_specs.items():
            fields[field] = self.get_field(obj, field, is_array)
        self.objects[obj] = fields

    def objects_to_str(self, filename = None):
        out = ''
        for obj, fields in self.objects.items():
            out += fields['name'] + '\n  ' + '\n  '.join(['%s: %s' % (field, value) for (field, value) in fields.items()]) + '\n'
        return out

class BlueTCL(tclwrapper.TCLWrapper):
    """Python wrapper for bluetcl."""

    def __init__(self, bluetcl_exe = 'bluetcl'):
        super().__init__(tcl_exe = bluetcl_exe)

    def get_virtual(self):
        return Virtual(self)

