# 描述符

描述符在 Python 的类型系统中扮演着一个非常重要的角色, property, `__slots__`, staticmethod, classmethod 等等都是通过描述符实现的. 

本文主要介绍描述符的底层原理, 关于如何使用描述符可以参考 Python 的官方文档或者下面的[参考资料](#参考资料)

## 基本数据结构和方法

PyDescrObject 是最基本的结构, 所有的 descriptor 都会包含它.

```c
// Include/descrobject.h

typedef struct {
    PyObject_HEAD
    PyTypeObject *d_type;   // descriptor 所在的类, 创建 descriptor 时被设置.
    PyObject *d_name;       // descriptor 的名字, 例如 `a = SomeDesc()`, 那么 d_name 就等于 a. 又例如 `__slots__ = ['a', 'b']`, d_name 就等于 a(或者 b).
    PyObject *d_qualname;
} PyDescrObject;

#define PyDescr_COMMON PyDescrObject d_common
```

descr_new 是基本的创建 descriptor 的方法.

```c
static PyDescrObject *
descr_new(PyTypeObject *descrtype, PyTypeObject *type, const char *name)
{
    PyDescrObject *descr;

    descr = (PyDescrObject *)PyType_GenericAlloc(descrtype, 0);
    if (descr != NULL) {
        Py_XINCREF(type);
        descr->d_type = type;
        descr->d_name = PyUnicode_InternFromString(name);
        if (descr->d_name == NULL) {
            Py_DECREF(descr);
            descr = NULL;
        }
        else {
            descr->d_qualname = NULL;
        }
    }
    return descr;
}
```

## PyMethodDescrObject

在 PyType_Ready 方法中, PyTypeObject 中的 tp_methods 成员会被转换为 PyMethodDescrObject, 然后保存在 tp_dict 中.

从结构上来看, PyMethodDescrObject 就是对 PyMethodDef 的简单包装. 

通过将 PyMethodDef 包装为一个 descriptor, 当想要调用对应的方法时都需要通过 descriptor 的 "中介" 方法, 即 tp_call.

```c
typedef struct {
    PyDescr_COMMON;
    PyMethodDef *d_method;
    vectorcallfunc vectorcall;
} PyMethodDescrObject;
```

```c
PyTypeObject PyMethodDescr_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "method_descriptor",
    sizeof(PyMethodDescrObject),
    0,
    (destructor)descr_dealloc,                  /* tp_dealloc */
    offsetof(PyMethodDescrObject, vectorcall),  /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)method_repr,                      /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    PyVectorcall_Call,                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC |
    Py_TPFLAGS_HAVE_VECTORCALL |
    Py_TPFLAGS_METHOD_DESCRIPTOR,               /* tp_flags */
    0,                                          /* tp_doc */
    descr_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    descr_methods,                              /* tp_methods */
    descr_members,                              /* tp_members */
    method_getset,                              /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    (descrgetfunc)method_get,                   /* tp_descr_get */
    0,                                          /* tp_descr_set */
};
/* This is for METH_CLASS in C, not for "f = classmethod(f)" in Python! */
PyTypeObject PyClassMethodDescr_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "classmethod_descriptor",
    sizeof(PyMethodDescrObject),
    0,
    (destructor)descr_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)method_repr,                      /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    (ternaryfunc)classmethoddescr_call,         /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    0,                                          /* tp_doc */
    descr_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    descr_methods,                              /* tp_methods */
    descr_members,                              /* tp_members */
    method_getset,                              /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    (descrgetfunc)classmethod_get,              /* tp_descr_get */
    0,                                          /* tp_descr_set */
};
```

注意: PyMethodDescr_Type 和 PyClassMethodDescr_Type 是类似的. PyClassMethodDescr_Type 是为了 CPython 内部的类方法准备的, 不是 Python 层面的 `@classmethod`.

### 创建 PyMethodDescrObject

不同类型的方法会设置不同的 `descr->vectorcall`.

```c
PyObject *
PyDescr_NewMethod(PyTypeObject *type, PyMethodDef *method)
{
    /* Figure out correct vectorcall function to use */
    vectorcallfunc vectorcall;
    switch (method->ml_flags & (METH_VARARGS | METH_FASTCALL | METH_NOARGS |
                                METH_O | METH_KEYWORDS | METH_METHOD))
    {
        case METH_VARARGS:
            vectorcall = method_vectorcall_VARARGS;
            break;
        case METH_VARARGS | METH_KEYWORDS:
            vectorcall = method_vectorcall_VARARGS_KEYWORDS;
            break;
        case METH_FASTCALL:
            vectorcall = method_vectorcall_FASTCALL;
            break;
        case METH_FASTCALL | METH_KEYWORDS:
            vectorcall = method_vectorcall_FASTCALL_KEYWORDS;
            break;
        case METH_NOARGS:
            vectorcall = method_vectorcall_NOARGS;
            break;
        case METH_O:
            vectorcall = method_vectorcall_O;
            break;
        case METH_METHOD | METH_FASTCALL | METH_KEYWORDS:
            vectorcall = method_vectorcall_FASTCALL_KEYWORDS_METHOD;
            break;
        default:
            PyErr_Format(PyExc_SystemError,
                         "%s() method: bad call flags", method->ml_name);
            return NULL;
    }

    PyMethodDescrObject *descr;

    descr = (PyMethodDescrObject *)descr_new(&PyMethodDescr_Type,
                                             type, method->ml_name);
    if (descr != NULL) {
        descr->d_method = method;
        descr->vectorcall = vectorcall;
    }
    return (PyObject *)descr;
}

PyObject *
PyDescr_NewClassMethod(PyTypeObject *type, PyMethodDef *method)
{
    PyMethodDescrObject *descr;

    descr = (PyMethodDescrObject *)descr_new(&PyClassMethodDescr_Type,
                                             type, method->ml_name);
    if (descr != NULL)
        descr->d_method = method;
    return (PyObject *)descr;
}
```

### tp_call/vectorcall

PyMethodDescrObject 支持 vectorcall, 最终调用的是 `descr->vectorcall`

以 method_vectorcall_VARARGS 为例:

```c
static inline funcptr
method_enter_call(PyThreadState *tstate, PyObject *func)
{
    if (_Py_EnterRecursiveCall(tstate, " while calling a Python object")) {
        return NULL;
    }
    return (funcptr)((PyMethodDescrObject *)func)->d_method->ml_meth;
}

static PyObject *
method_vectorcall_VARARGS(
    PyObject *func, PyObject *const *args, size_t nargsf, PyObject *kwnames)
{
    PyThreadState *tstate = _PyThreadState_GET();
    Py_ssize_t nargs = PyVectorcall_NARGS(nargsf);
    if (method_check_args(func, args, nargs, kwnames)) {
        return NULL;
    }
    PyObject *argstuple = _PyTuple_FromArray(args+1, nargs-1);
    if (argstuple == NULL) {
        return NULL;
    }
    PyCFunction meth = (PyCFunction)method_enter_call(tstate, func);
    if (meth == NULL) {
        Py_DECREF(argstuple);
        return NULL;
    }
    PyObject *result = meth(args[0], argstuple);
    Py_DECREF(argstuple);
    _Py_LeaveRecursiveCall(tstate);
    return result;
}
```

可以看到, 最终调用的是 `descr->d_method->ml_meth`.

PyClassMethodDescr_Type 的 tp_call 如下:

```c
* Instances of classmethod_descriptor are unlikely to be called directly.
   For one, the analogous class "classmethod" (for Python classes) is not
   callable. Second, users are not likely to access a classmethod_descriptor
   directly, since it means pulling it from the class __dict__.

   This is just an excuse to say that this doesn't need to be optimized:
   we implement this simply by calling __get__ and then calling the result.

    一个例子: dict.fromkeys('abc') 会直接调用 descr 的 classmethod_get, 而不会调用 classmethoddescr_call.
   但是, dict.__dict__['fromkeys'](dict, 'abc') 就会调用 classmethoddescr_call.
*/
static PyObject *
classmethoddescr_call(PyMethodDescrObject *descr, PyObject *args,
                      PyObject *kwds)
{
    Py_ssize_t argc = PyTuple_GET_SIZE(args);
    if (argc < 1) {
        PyErr_Format(PyExc_TypeError,
                     "descriptor '%V' of '%.100s' "
                     "object needs an argument",
                     descr_name((PyDescrObject *)descr), "?",
                     PyDescr_TYPE(descr)->tp_name);
        return NULL;
    }
    PyObject *self = PyTuple_GET_ITEM(args, 0);
    // bound 是一个 PyCMethodObject
    PyObject *bound = classmethod_get(descr, NULL, self);
    if (bound == NULL) {
        return NULL;
    }
    PyObject *res = PyObject_VectorcallDict(bound, _PyTuple_ITEMS(args)+1,
                                           argc-1, kwds);
    Py_DECREF(bound);
    return res;
}
```

通过上述代码可以知道 CPython 内部是如何调用 C 编写的类方法的, 注意这和 Python 层面的 classmethod 不一样.

## PyMemberDescrObject

在 PyType_Ready 方法中, PyTypeObject 中的 tp_members 成员会被转换为 PyMemberDescrObject, 然后保存在 tp_dict 中.

从结构上来看, PyMemberDescrObject 就是对 PyMemberDef 的简单包装. 

通过将 PyMemberDef 包装为一个 descriptor, 想要访问属性时都需要通过 descriptor 的 "中介" 方法, 即 tp_descr_get 和 tp_descr_set.

Python 层面的 `__slots__` 和 descriptor 成员都是通过 PyMemberDescrObject 实现的.

PyMemberDescrObject:

```c
// Include/descrobject.h

typedef struct {
    PyDescr_COMMON;
    struct PyMemberDef *d_member;
} PyMemberDescrObject;
```

PyMemberDescr_Type:

```c
PyTypeObject PyMemberDescr_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "member_descriptor",
    sizeof(PyMemberDescrObject),
    0,
    (destructor)descr_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)member_repr,                      /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    0,                                          /* tp_doc */
    descr_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    descr_methods,                              /* tp_methods */
    descr_members,                              /* tp_members */
    member_getset,                              /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    (descrgetfunc)member_get,                   /* tp_descr_get */
    (descrsetfunc)member_set,                   /* tp_descr_set */
};
```

### 创建 PyMemberDescrObject

PyDescr_NewMember 方法:

```c
// Objects/descrobject.c

PyObject *
PyDescr_NewMember(PyTypeObject *type, PyMemberDef *member)
{
    PyMemberDescrObject *descr;

    descr = (PyMemberDescrObject *)descr_new(&PyMemberDescr_Type,
                                             type, member->name);
    if (descr != NULL)
        descr->d_member = member;
    return (PyObject *)descr;
}
```

### PyMemberDescrObject 的 get/set

member_get:

```c
// Objects/descrobject.c

static PyObject *
member_get(PyMemberDescrObject *descr, PyObject *obj, PyObject *type)
{
    PyObject *res;

    if (descr_check((PyDescrObject *)descr, obj, &res))
        return res;

    if (descr->d_member->flags & READ_RESTRICTED) {
        if (PySys_Audit("object.__getattr__", "Os",
            obj ? obj : Py_None, descr->d_member->name) < 0) {
            return NULL;
        }
    }

    return PyMember_GetOne((char *)obj, descr->d_member);
}
```

```c
// Python/structmember.c
// 有删减

PyObject *
PyMember_GetOne(const char *addr, PyMemberDef *l)
{
    PyObject *v;

    addr += l->offset;
    switch (l->type) {
    case T_BOOL:
        v = PyBool_FromLong(*(char*)addr);
        break;
    case T_BYTE:
        v = PyLong_FromLong(*(char*)addr);
        break;
    case T_INT:
        v = PyLong_FromLong(*(int*)addr);
        break;
    case T_OBJECT:
        v = *(PyObject **)addr;
        if (v == NULL)
            v = Py_None;
        Py_INCREF(v);
        break;
    case T_OBJECT_EX:
        v = *(PyObject **)addr;
        if (v == NULL)
            PyErr_SetString(PyExc_AttributeError, l->name);
        Py_XINCREF(v);
        break;
    default:
        PyErr_SetString(PyExc_SystemError, "bad memberdescr type");
        v = NULL;
    }
    return v;
}
```

member_set:

```c
// Objects/descrobject.c

static int
member_set(PyMemberDescrObject *descr, PyObject *obj, PyObject *value)
{
    int res;

    if (descr_setcheck((PyDescrObject *)descr, obj, value, &res))
        return res;
    return PyMember_SetOne((char *)obj, descr->d_member, value);
}
```

```c
// Python/structmember.c
// 有删减

int
PyMember_SetOne(char *addr, PyMemberDef *l, PyObject *v)
{
    PyObject *oldv;

    addr += l->offset;

    if ((l->flags & READONLY))
    {
        PyErr_SetString(PyExc_AttributeError, "readonly attribute");
        return -1;
    }
    if (v == NULL) {
        if (l->type == T_OBJECT_EX) {
            /* Check if the attribute is set. */
            if (*(PyObject **)addr == NULL) {
                PyErr_SetString(PyExc_AttributeError, l->name);
                return -1;
            }
        }
        else if (l->type != T_OBJECT) {
            PyErr_SetString(PyExc_TypeError,
                            "can't delete numeric/char attribute");
            return -1;
        }
    }
    switch (l->type) {
    case T_OBJECT:
    case T_OBJECT_EX:
        Py_XINCREF(v);
        oldv = *(PyObject **)addr;
        *(PyObject **)addr = v;
        Py_XDECREF(oldv);
        break;
    default:
        PyErr_Format(PyExc_SystemError,
                     "bad memberdescr type for %s", l->name);
        return -1;
    }
    return 0;
}
```

## PyGetSetDescrObject

PyGetSetDescrObject 是对 PyGetSetDef 的简单包装, 感觉和 PyMemberDescrObject 类似, 都是用于属性访问的.

在 PyType_Ready 方法中会调用 add_getset 方法将 PyGetSetDef 转换为 PyGetSetDescrObject, 然后添加到 tp_dict 中.

```c
typedef struct {
    PyDescr_COMMON;
    PyGetSetDef *d_getset;
} PyGetSetDescrObject;
```

```c
PyTypeObject PyGetSetDescr_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "getset_descriptor",
    sizeof(PyGetSetDescrObject),
    0,
    (destructor)descr_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)getset_repr,                      /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    0,                                          /* tp_doc */
    descr_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    0,                                          /* tp_methods */
    descr_members,                              /* tp_members */
    getset_getset,                              /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    (descrgetfunc)getset_get,                   /* tp_descr_get */
    (descrsetfunc)getset_set,                   /* tp_descr_set */
};
```

### 一个常见的例子

```py
class C:
    pass

c = ()
c.__dict__
```

在上面的代码中, 元类在创建类 C 时, type_new 方法会设置类 C 的 tp_getset, 接着在 PyType_Ready 方法中会将 tp_getset 转换为 PyGetSetDescrObject.

部分代码如下:

```c
// type_new
if (type->tp_weaklistoffset && type->tp_dictoffset)
    type->tp_getset = subtype_getsets_full;
else if (type->tp_weaklistoffset && !type->tp_dictoffset)
    type->tp_getset = subtype_getsets_weakref_only;
else if (!type->tp_weaklistoffset && type->tp_dictoffset)
    type->tp_getset = subtype_getsets_dict_only;
else
    type->tp_getset = NULL;

// PyType_Ready
if (type->tp_getset != NULL) {
    if (add_getset(type, type->tp_getset) < 0)
        goto error;
}
```

以 subtype_getsets_full 为例:

```c
static PyGetSetDef subtype_getsets_full[] = {
    {"__dict__", subtype_dict, subtype_setdict,
     PyDoc_STR("dictionary for instance variables (if defined)")},
    {"__weakref__", subtype_getweakref, NULL,
     PyDoc_STR("list of weak references to the object (if defined)")},
    {0}
};
```

subtype_getsets_full 中定义了 `__dict__` 和 `__weakref__`. 当实例 c 访问 `__dict__` 时, 就会调用 PyGetSetDescrObject 的 tp_descr_get(即 getset_get), 接着 tp_descr_get 又会调用 subtype_dict.

## PyWrapperDescrObject

PyWrapperDescrObject 和 slot 的实现有关.

从结构来看, PyWrapperDescrObject 其实就是对 slotdef 的简单包装.

在 PyType_Ready 方法中会调用 add_operators 方法将 slotdef 转换为 PyWrapperDescrObject, 然后添加到 tp_dict 中.

通过将 slotdef 包装为一个 descriptor, 当想要调用对应的方法时都需要通过 descriptor 的 "中介" 方法, 即 tp_call.

```c
// Include/descrobject.h

/* 在 typeobject.c 中有 `typedef struct wrapperbase slotdef;` */
struct wrapperbase {
    const char *name;
    int offset;
    void *function;
    wrapperfunc wrapper;
    const char *doc;
    int flags;
    PyObject *name_strobj;
};

typedef struct {
    PyDescr_COMMON;
    struct wrapperbase *d_base;   // 一般指向 slotdef
    void *d_wrapped; /* This can be any function pointer, 对于 slotdef 来说, 就是 slotptr(type, slotdef.offset) */
} PyWrapperDescrObject;
```

```c
// Objects/descrobject.c

PyTypeObject PyWrapperDescr_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "wrapper_descriptor",
    sizeof(PyWrapperDescrObject),
    0,
    (destructor)descr_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)wrapperdescr_repr,                /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    (ternaryfunc)wrapperdescr_call,             /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC |
    Py_TPFLAGS_METHOD_DESCRIPTOR,               /* tp_flags */
    0,                                          /* tp_doc */
    descr_traverse,                             /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    descr_methods,                              /* tp_methods */
    descr_members,                              /* tp_members */
    wrapperdescr_getset,                        /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    (descrgetfunc)wrapperdescr_get,             /* tp_descr_get */
    0,                                          /* tp_descr_set */
};
```

### 创建 PyWrapperDescrObject

```c
// Objects/descrobject.c

/* 这里的 base 一般就是 slotdef, 而 wrapped 就是 slotdef 中的 offset 指向类中的方法
   可以看看 typeobject.c 中的 add_operators 方法是如何调用本方法的.
*/
PyObject *
PyDescr_NewWrapper(PyTypeObject *type, struct wrapperbase *base, void *wrapped)
{
    PyWrapperDescrObject *descr;

    descr = (PyWrapperDescrObject *)descr_new(&PyWrapperDescr_Type,
                                             type, base->name);
    if (descr != NULL) {
        descr->d_base = base;
        descr->d_wrapped = wrapped;
    }
    return (PyObject *)descr;
}
```

### 调用 PyWrapperDescrObject(__call__)

PyWrapperDescr_Type 的 tp_call 设置为 wrapperdescr_call. wrapperdescr_call 接下来的调用链为 `descr->d_base->wrapper` -> `descr->d_wrapped`.

```c
// Objects/descrobject.c

Py_LOCAL_INLINE(PyObject *)
wrapperdescr_raw_call(PyWrapperDescrObject *descr, PyObject *self,
                      PyObject *args, PyObject *kwds)
{
    wrapperfunc wrapper = descr->d_base->wrapper;

    if (descr->d_base->flags & PyWrapperFlag_KEYWORDS) {
        wrapperfunc_kwds wk = (wrapperfunc_kwds)(void(*)(void))wrapper;
        return (*wk)(self, args, descr->d_wrapped, kwds);
    }

    if (kwds != NULL && (!PyDict_Check(kwds) || PyDict_GET_SIZE(kwds) != 0)) {
        PyErr_Format(PyExc_TypeError,
                     "wrapper %s() takes no keyword arguments",
                     descr->d_base->name);
        return NULL;
    }
    return (*wrapper)(self, args, descr->d_wrapped);
}

static PyObject *
wrapperdescr_call(PyWrapperDescrObject *descr, PyObject *args, PyObject *kwds)
{
    Py_ssize_t argc;
    PyObject *self, *result;

    /* Make sure that the first argument is acceptable as 'self' */
    assert(PyTuple_Check(args));
    argc = PyTuple_GET_SIZE(args);
    if (argc < 1) {
        PyErr_Format(PyExc_TypeError,
                     "descriptor '%V' of '%.100s' "
                     "object needs an argument",
                     descr_name((PyDescrObject *)descr), "?",
                     PyDescr_TYPE(descr)->tp_name);
        return NULL;
    }
    self = PyTuple_GET_ITEM(args, 0);
    if (!_PyObject_RealIsSubclass((PyObject *)Py_TYPE(self),
                                  (PyObject *)PyDescr_TYPE(descr))) {
        PyErr_Format(PyExc_TypeError,
                     "descriptor '%V' "
                     "requires a '%.100s' object "
                     "but received a '%.100s'",
                     descr_name((PyDescrObject *)descr), "?",
                     PyDescr_TYPE(descr)->tp_name,
                     Py_TYPE(self)->tp_name);
        return NULL;
    }

    args = PyTuple_GetSlice(args, 1, argc);
    if (args == NULL) {
        return NULL;
    }
    result = wrapperdescr_raw_call(descr, self, args, kwds);
    Py_DECREF(args);
    return result;
}
```

## 参考资料

- [https://docs.python.org/3/reference/datamodel.html#implementing-descriptors](https://docs.python.org/3/reference/datamodel.html#implementing-descriptors)

- [https://docs.python.org/3/howto/descriptor.html](https://docs.python.org/3/howto/descriptor.html)