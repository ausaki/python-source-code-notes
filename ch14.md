# Python模块的动态加载机制

## import/ from xxx import xxx

各种 import 语法：

```py
import package
import module
import package.module

from package import a
from package import module
from package.module import a
```

```py
import P
import P.m
import P as P1

from P import m
from P.m import a
from P.m import a as a1
```


```bash
.
└── P
    ├── __init__.py
    ├── __init__.pyc
    └── m.py

1 directory, 3 files
```

```py
>>> import sys
>>> import P
hello from P.__init__.py
>>> dir(P)
['__builtins__', '__doc__', '__file__', '__name__', '__package__', '__path__']
>>> import P.a
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ImportError: No module named a
>>> import P.m
>>> dir(P)
['__builtins__', '__doc__', '__file__', '__name__', '__package__', '__path__', 'm']
>>> dir(P.m)
['__builtins__', '__doc__', '__file__', '__name__', '__package__']
>>> sys.modules['P']
<module 'P' from 'P/__init__.pyc'>
>>> sys.modules['P.m']
<module 'P.m' from 'P/m.pyc'>

```

## import 机制

```C
case IMPORT_NAME:
    w = GETITEM(names, oparg);
    x = PyDict_GetItemString(f->f_builtins, "__import__");
    if (x == NULL) {
        PyErr_SetString(PyExc_ImportError,
                "__import__ not found");
        break;
    }
    v = POP();
    u = TOP();
    if (PyInt_AsLong(u) != -1 || PyErr_Occurred())
        w = PyTuple_Pack(5,
                w,
                f->f_globals,
                f->f_locals == NULL ?
                    Py_None : f->f_locals,
                v,
                u);
    else
        w = PyTuple_Pack(4,
                w,
                f->f_globals,
                f->f_locals == NULL ?
                    Py_None : f->f_locals,
                v);
    Py_DECREF(v);
    Py_DECREF(u);
    if (w == NULL) {
        u = POP();
        x = NULL;
        break;
    }
    READ_TIMESTAMP(intr0);
    x = PyEval_CallObject(x, w);
    READ_TIMESTAMP(intr1);
    Py_DECREF(w);
    SET_TOP(x);
    if (x != NULL) continue;
    break;
```
import 的流程比较复杂，详情请查看源代码和原文。