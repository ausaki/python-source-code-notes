# -*- coding: utf-8 -*-

"""
解析.pyc 文件
用法：python parse_pyc.py xxx.pyc
"""

import sys
import struct

TYPE_NULL = '0'
TYPE_NONE = 'N'
TYPE_FALSE = 'F'
TYPE_TRUE = 'T'
TYPE_STOPITER = 'S'
TYPE_ELLIPSIS = '.'
TYPE_INT = 'i'
TYPE_INT64 = 'I'
TYPE_FLOAT = 'f'
TYPE_BINARY_FLOAT = 'g'
TYPE_COMPLEX = 'x'
TYPE_BINARY_COMPLEX = 'y'
TYPE_LONG = 'l'
TYPE_STRING = 's'
TYPE_INTERNED = 't'
TYPE_STRINGREF = 'R'
TYPE_TUPLE = '('
TYPE_LIST = '['
TYPE_DICT = '{'
TYPE_CODE = 'c'
TYPE_UNICODE = 'u'
TYPE_UNKNOWN = '?'
TYPE_SET = '<'
TYPE_FROZENSET = '>'

strlist = []


class NULL(object):
    pass


null = NULL()


class Code(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __str__(self):
        keys = [
            'argcount',
            'nlocals',
            'stacksize',
            'flags',
            'code',
            'consts',
            'names',
            'varnames',
            'freevars',
            'cellvars',
            'filename',
            'name',
            'firstlineno',
            'lnotab'
        ]
        s = 'code(\n'
        for k in keys:
            v = getattr(self, k)
            if k == 'code':
                v = '0x' + v.encode('hex')
            s += '\t{} = {}'.format(k, v)
            s += '\n'
        s += ')'
        return s

def r_byte(fp):
    return ord(fp.read(1))


def r_short(fp):
    p = struct.unpack('<h', fp.read(2))
    return p[0]


def r_int(fp):
    p = struct.unpack('<I', fp.read(4))
    return p[0]


def r_long(fp):
    return r_int(fp)


def r_int64(fp):
    lo = r_int(fp)
    hi = r_int(fp)
    return hi << 32 | lo


def r_object(fp):

    type_ = fp.read(1)

    if type_ == TYPE_NONE:
        return None
    elif type_ == TYPE_NULL:
        return null
    elif type_ == TYPE_STOPITER:
        return 'Stopiteration'
    elif type_ == TYPE_ELLIPSIS:
        return 'Ellipsis'
    elif type_ == TYPE_FALSE:
        return False
    elif type_ == TYPE_TRUE:
        return True
    elif type_ == TYPE_INT:
        return r_int(fp)
    elif type_ == TYPE_INT64:
        return r_int64(fp)
    elif type_ == TYPE_LONG:
        n = r_int(fp)
        size = -n if n < 0 else n
        digits = []
        for i in range(size):
            digits.append(r_short(fp))
        return 'long({}, {})'.format(n, digits)
    elif type_ == TYPE_FLOAT:
        n = r_byte(fp)
        buff = fp.read(n)
        return 'float({}, {!r})'.format(n, buff)
    elif type_ == TYPE_INTERNED or type_ == TYPE_STRING:
        n = r_int(fp)
        s = fp.read(n)
        if type_ == TYPE_INTERNED:
            strlist.append(s)
        return s
    elif type_ == TYPE_STRINGREF:
        n = r_int(fp)
        return strlist[n]
    elif type_ == TYPE_UNICODE:
        n = r_int(fp)
        s = fp.read(n)
        return s.decode('utf8')
    elif type_ == TYPE_TUPLE:
        n = r_int(fp)
        t = []
        for i in range(n):
            o = r_object(fp)
            t.append(o)
        return tuple(t)
    elif type_ == TYPE_LIST:
        n = r_int(fp)
        l = []
        for i in range(n):
            o = r_object(fp)
            t.append(o)
        return l
    elif type_ == TYPE_DICT:
        d = {}
        while True:
            key = r_object(fp)
            if key == null:
                break
            val = r_object(fp)
            d[key] = val
        return d
    elif type_ == TYPE_SET or type_ == TYPE_FROZENSET:
        n = r_int(fp)
        s = set()
        for i in range(n):
            o = r_object(fp)
            s.add(o)
        return s
    elif type_ == TYPE_CODE:
        argcount = r_long(fp)
        nlocals = r_long(fp)
        stacksize = r_long(fp)
        flags = r_long(fp)
        code = r_object(fp)
        consts = r_object(fp)
        names = r_object(fp)
        varnames = r_object(fp)
        freevars = r_object(fp)
        cellvars = r_object(fp)
        filename = r_object(fp)
        name = r_object(fp)
        firstlineno = r_long(fp)
        lnotab = r_object(fp)
        return Code(
            argcount=argcount,
            nlocals=nlocals,
            stacksize=stacksize,
            flags=flags,
            code=code,
            consts=consts,
            names=names,
            varnames=varnames,
            freevars=freevars,
            cellvars=cellvars,
            filename=filename,
            name=name,
            firstlineno=firstlineno,
            lnotab=lnotab
        )
    elif type_ == TYPE_LIST:
        n = r_int(fp)
        l = []
        for i in range(n):
            o = r_object(fp)
            t.append(o)
        return l


if __name__ == '__main__':
    pyc_file = sys.argv[1]
    fp = open(pyc_file, 'rb')
    # 读取 magic：long
    magic = r_int(fp)
    print 'magic:', magic

    # 读取 mtime
    mtime = r_int(fp)
    print 'mtime:', mtime

    # 读取PyCodeObject
    code_obj = r_object(fp)
    print 'code obj:', code_obj
    fp.close()
