# -*- coding: utf-8 -*-
import sys
import os
import dis

pyfile = sys.argv[1]
f_name = os.path.basename(pyfile)

fp = open(pyfile)
src = fp.read()
fp.close()

codeobj = compile(src, f_name, 'exec')

def print_indent(s, indent):
    if indent == 0:
        print s
    else:
        print ' ' * (4 * indent), s

def display(codeobj, indent=0):
    info_keys = [
        'co_filename',
        'co_name',
        'co_firstlineno',
        'co_flags',
        'co_lnotab',
        'co_names',
        'co_argcount',
        'co_nlocals',
        'co_varnames',
        'co_consts',
        'co_cellvars',
        'co_freevars',
        'co_code',
        'co_stacksize',
    ]
    print_indent('[code obj info] - [%s]' % codeobj.co_name, indent)
    for k in info_keys:
        v = getattr(codeobj, k)
        if k == 'co_code':
            print_indent(k + ': ', indent)
            codes = dis.dis(codeobj)
            if codes is not None:
                for l in codes.splitlines():
                    print_indent(l, indent)
        elif k == 'co_consts':
            print_indent(k + ': ', indent)
            for const in v:
                if hasattr(const, 'co_code'):
                    display(const, indent + 1) 
                else:
                    print_indent(const, indent)
        else:
            print_indent(k + ': ' + str(v), indent)

display(codeobj)

