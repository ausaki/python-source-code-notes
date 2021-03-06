# 类型系统之 super

super 在 CPython 内部其实是一个类, 并不是函数.

```c
// Objects/typeobject.c

typedef struct {
    PyObject_HEAD
    PyTypeObject *type;
    PyObject *obj;
    PyTypeObject *obj_type;
} superobject;
```

```c
// Objects/typeobject.c

PyTypeObject PySuper_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "super",                                    /* tp_name */
    sizeof(superobject),                        /* tp_basicsize */
    0,                                          /* tp_itemsize */
    /* methods */
    super_dealloc,                              /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    super_repr,                                 /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    super_getattro,                             /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC |
        Py_TPFLAGS_BASETYPE,                    /* tp_flags */
    super_doc,                                  /* tp_doc */
    super_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    0,                                          /* tp_methods */
    super_members,                              /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    super_descr_get,                            /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    super_init,                                 /* tp_init */
    PyType_GenericAlloc,                        /* tp_alloc */
    PyType_GenericNew,                          /* tp_new */
    PyObject_GC_Del,                            /* tp_free */
};
```

从 superobject 的结构可以看出, superobject 是一个包裹了类型信息(type 和 object) 的一个对象, 和描述符非常类似.

当通过 `super().xxx` 访问父类的属性时, 实际上负责获取属性的是 PySuper_Type 的 tp_getattro, 即 super_getattro 方法. 

### super_init

```c
// Objects/typeobject.c

static int
super_init(PyObject *self, PyObject *args, PyObject *kwds)
{
    superobject *su = (superobject *)self;
    PyTypeObject *type = NULL;
    PyObject *obj = NULL;
    PyTypeObject *obj_type = NULL;

    if (!_PyArg_NoKeywords("super", kwds))
        return -1;
    if (!PyArg_ParseTuple(args, "|O!O:super", &PyType_Type, &type, &obj))
        return -1;

    if (type == NULL) {
        /* Call super(), without args -- fill in from __class__
           and first local variable on the stack. */
        PyThreadState *tstate = _PyThreadState_GET();
        PyFrameObject *frame = PyThreadState_GetFrame(tstate);
        if (frame == NULL) {
            PyErr_SetString(PyExc_RuntimeError,
                            "super(): no current frame");
            return -1;
        }

        PyCodeObject *code = PyFrame_GetCode(frame);
        int res = super_init_without_args(frame, code, &type, &obj);
        Py_DECREF(frame);
        Py_DECREF(code);

        if (res < 0) {
            return -1;
        }
    }

    if (obj == Py_None)
        obj = NULL;
    if (obj != NULL) {
        obj_type = supercheck(type, obj);
        if (obj_type == NULL)
            return -1;
        Py_INCREF(obj);
    }
    Py_INCREF(type);
    Py_XSETREF(su->type, type);
    Py_XSETREF(su->obj, obj);
    Py_XSETREF(su->obj_type, obj_type);
    return 0;
}
```

### "super() 无参数调用" 的实现原理

以下面的 Python 代码为例:

```py
class A:
    def __init__(self):
        super().__init__()

A()
```

对应的字节码如下:

```
  4          14 LOAD_BUILD_CLASS
             16 LOAD_CONST               3 (<code object A at 0x7fa9d94c6be0, file "mydemo/class_demo.py", line 4>)
             18 LOAD_CONST               4 ('A')
             20 MAKE_FUNCTION            0
             22 LOAD_CONST               4 ('A')
             24 CALL_FUNCTION            2
             26 STORE_NAME               2 (A)

  8          28 LOAD_NAME                2 (A)
             30 CALL_FUNCTION            0
             32 POP_TOP
             34 LOAD_CONST               1 (None)
             36 RETURN_VALUE

Disassembly of <code object A at 0x7fa9d94c6be0, file "mydemo/class_demo.py", line 4>:
  4           0 LOAD_NAME                0 (__name__)
              2 STORE_NAME               1 (__module__)
              4 LOAD_CONST               0 ('A')
              6 STORE_NAME               2 (__qualname__)

  5           8 LOAD_CLOSURE             0 (__class__)
             10 BUILD_TUPLE              1
             12 LOAD_CONST               1 (<code object __init__ at 0x7fa9d94c6b30, file "mydemo/class_demo.py", line 5>)
             14 LOAD_CONST               2 ('A.__init__')
             16 MAKE_FUNCTION            8 (closure)
             18 STORE_NAME               3 (__init__)
             20 LOAD_CLOSURE             0 (__class__)
             22 DUP_TOP
             24 STORE_NAME               4 (__classcell__)
             26 RETURN_VALUE

Disassembly of <code object __init__ at 0x7fa9d94c6b30, file "mydemo/class_demo.py", line 5>:
  6           0 LOAD_GLOBAL              0 (super)
              2 CALL_FUNCTION            0
              4 LOAD_METHOD              1 (__init__)
              6 CALL_METHOD              0
              8 POP_TOP
             10 LOAD_CONST               0 (None)
             12 RETURN_VALUE
```

Python 为了支持 super() 无参数调用, 在编译字节码对象时做了一些额外的工作, 如下:

- class A 的字节码对象的 co_cellvars 的长度等于 1, 保存的就是 `__class__`.

- 在创建 `__init__` 函数时, 通过 LOAD_CLOSURE 加载 `__class__` 到栈上. 可以看到 `__init__` 实际上是一个闭包函数.

当调用 `__init__` 时, `frame->f_fastlocals` 的布局如下:

```
__init__'s args | cellvars | freevars | local vars | stack
```

接下来来看对应的 CPython 代码:

```c
/* 调用形式为 super(), 既然用户没有提供参数, 则尝试从 frame stack 上获取参数. 
   这个功能依赖于字节码的协助, 在出现 super() 的代码, Python 会生成和 __class__ 相关的字节码.
   详情参考笔记 "类型系统之元类" 和 "类型系统之super".

   frame->f_fastlocals 的布局: __init__'s args | cellvars | freevars | local vars | stack
*/
static int
super_init_without_args(PyFrameObject *f, PyCodeObject *co,
                        PyTypeObject **type_p, PyObject **obj_p)
{
    if (co->co_argcount == 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        "super(): no arguments");
        return -1;
    }
    
    // f->f_localsplus[0] 是 __init__(self, *args, **kwargs) 中的 self
    PyObject *obj = f->f_localsplus[0];
    Py_ssize_t i, n;
    if (obj == NULL && co->co_cell2arg) {
        /* The first argument might be a cell. */
        n = PyTuple_GET_SIZE(co->co_cellvars);
        for (i = 0; i < n; i++) {
            if (co->co_cell2arg[i] == 0) {
                PyObject *cell = f->f_localsplus[co->co_nlocals + i];
                assert(PyCell_Check(cell));
                obj = PyCell_GET(cell);
                break;
            }
        }
    }
    if (obj == NULL) {
        PyErr_SetString(PyExc_RuntimeError,
                        "super(): arg[0] deleted");
        return -1;
    }

    if (co->co_freevars == NULL) {
        n = 0;
    }
    else {
        assert(PyTuple_Check(co->co_freevars));
        n = PyTuple_GET_SIZE(co->co_freevars);
    }

    PyTypeObject *type = NULL;
    for (i = 0; i < n; i++) {
        PyObject *name = PyTuple_GET_ITEM(co->co_freevars, i);
        assert(PyUnicode_Check(name));
        if (_PyUnicode_EqualToASCIIId(name, &PyId___class__)) {
            Py_ssize_t index = co->co_nlocals +
                PyTuple_GET_SIZE(co->co_cellvars) + i;
            PyObject *cell = f->f_localsplus[index];
            if (cell == NULL || !PyCell_Check(cell)) {
                PyErr_SetString(PyExc_RuntimeError,
                  "super(): bad __class__ cell");
                return -1;
            }
            type = (PyTypeObject *) PyCell_GET(cell);
            if (type == NULL) {
                PyErr_SetString(PyExc_RuntimeError,
                  "super(): empty __class__ cell");
                return -1;
            }
            if (!PyType_Check(type)) {
                PyErr_Format(PyExc_RuntimeError,
                  "super(): __class__ is not a type (%s)",
                  Py_TYPE(type)->tp_name);
                return -1;
            }
            break;
        }
    }
    if (type == NULL) {
        PyErr_SetString(PyExc_RuntimeError,
                        "super(): __class__ cell not found");
        return -1;
    }

    *type_p = type;
    *obj_p = obj;
    return 0;
}
```

简单来说, 从 `f->f_localsplus[0]` 对应的参数是 `__init__` 的 self, self 对应 super 的第二个参数. 再从 freevars 中获取 super 的第一个参数(`__class__`).

super() 只在特定的地方调用才合法, 例如实例方法, 类方法.

### 属性访问

```c
static PyObject *
super_getattro(PyObject *self, PyObject *name)
{
    superobject *su = (superobject *)self;
    PyTypeObject *starttype;
    PyObject *mro;
    Py_ssize_t i, n;

    starttype = su->obj_type;
    if (starttype == NULL)
        goto skip;

    /* We want __class__ to return the class of the super object
       (i.e. super, or a subclass), not the class of su->obj. */
    if (PyUnicode_Check(name) &&
        PyUnicode_GET_LENGTH(name) == 9 &&
        _PyUnicode_EqualToASCIIId(name, &PyId___class__))
        goto skip;

    mro = starttype->tp_mro;
    if (mro == NULL)
        goto skip;

    assert(PyTuple_Check(mro));
    n = PyTuple_GET_SIZE(mro);

    /* No need to check the last one: it's gonna be skipped anyway. mro 的最后一个元素是 object 
       获取 starttype->tp_mro 中位于 su->type 后面的第一个父类.
       对于 super(MyClass, self) 来说, 目标指向 MyClass.__mro__ 的第二个元素.
    */
    for (i = 0; i+1 < n; i++) {
        if ((PyObject *)(su->type) == PyTuple_GET_ITEM(mro, i))
            break;
    }
    i++;  /* skip su->type (if any)  */
    if (i >= n)
        goto skip;

    /* keep a strong reference to mro because starttype->tp_mro can be
       replaced during PyDict_GetItemWithError(dict, name)  */
    Py_INCREF(mro);
    do {
        PyObject *res, *tmp, *dict;
        descrgetfunc f;

        tmp = PyTuple_GET_ITEM(mro, i);
        assert(PyType_Check(tmp));

        dict = ((PyTypeObject *)tmp)->tp_dict;
        assert(dict != NULL && PyDict_Check(dict));

        res = PyDict_GetItemWithError(dict, name);
        if (res != NULL) {
            Py_INCREF(res);

            f = Py_TYPE(res)->tp_descr_get;
            if (f != NULL) {
                tmp = f(res,
                    /* Only pass 'obj' param if this is instance-mode super
                       (See SF ID #743627)  */
                    (su->obj == (PyObject *)starttype) ? NULL : su->obj,
                    (PyObject *)starttype);
                Py_DECREF(res);
                res = tmp;
            }

            Py_DECREF(mro);
            return res;
        }
        else if (PyErr_Occurred()) {
            Py_DECREF(mro);
            return NULL;
        }

        i++;
    } while (i < n);
    Py_DECREF(mro);

  skip:
    return PyObject_GenericGetAttr(self, name);
}
```

## 参考

- [Python 关于 super 的文档](https://docs.python.org/3/library/functions.html#super)
- 