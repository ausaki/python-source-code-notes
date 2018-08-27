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

print 'f_consts:', codeobj.co_consts
print 'code:', codeobj.co_code.encode('hex')
print 'lnotab:', codeobj.co_lnotab

print dis.dis(codeobj)