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

def display(codeobj):
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
    print 'code obj info:'
    for k in info_keys:
        v = getattr(codeobj, k)
        print k, ':',
        if k == 'co_code':
            print
            print dis.dis(codeobj)
        elif k == 'co_consts':
            print
            for const in v:
                if hasattr(const, 'co_code'):
                    print '----'
                    display(const) 
                    print '----'
                else:
                    print const
        else:
            print v


display(codeobj)

