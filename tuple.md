# Tuple

PyTupleObject:

```c
typedef struct {
    PyObject_VAR_HEAD
    /* ob_item contains space for 'ob_size' elements.
       Items must normally not be NULL, except during construction when
       the tuple is not yet visible outside the function that builds it. */
    PyObject *ob_item[1];
} PyTupleObject;

PyTypeObject PyTuple_Type = {
    /* PyVarObject
    {
        {
            1,              // ob_refcnt
            &PyType_Type,   // ob_type
        }, // ob_base(PyObject)
        0,                  // ob_size     
    }
    */
    PyVarObject_HEAD_INIT(&PyType_Type, 0) 
    "tuple",                                    /* tp_name */
    sizeof(PyTupleObject) - sizeof(PyObject *), /* tp_basicsize */
    sizeof(PyObject *),                         /* tp_itemsize */
    (destructor)tupledealloc,                   /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)tuplerepr,                        /* tp_repr */
    0,                                          /* tp_as_number */
    &tuple_as_sequence,                         /* tp_as_sequence */
    &tuple_as_mapping,                          /* tp_as_mapping */
    (hashfunc)tuplehash,                        /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC |
        Py_TPFLAGS_BASETYPE | Py_TPFLAGS_TUPLE_SUBCLASS, /* tp_flags */
    tuple_new__doc__,                           /* tp_doc */
    (traverseproc)tupletraverse,                /* tp_traverse */
    0,                                          /* tp_clear */
    tuplerichcompare,                           /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    tuple_iter,                                 /* tp_iter */
    0,                                          /* tp_iternext */
    tuple_methods,                              /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    0,                                          /* tp_init */
    0,                                          /* tp_alloc */
    tuple_new,                                  /* tp_new */
    PyObject_GC_Del,                            /* tp_free */
    .tp_vectorcall = tuple_vectorcall,
};
```


注意, PyTupleObject 中的 ob_item 实际上不占据 PyTupleObject 对象的空间, ob_item 是为了方便访问变长元素空间而设置的. 这一点可以从 PyTuple_Type 的 tp_basicsize 看出来, `tp_basicsize = sizeof(PyTupleObject) - sizeof(PyObject *)`.

PyTupleObject 的内存布局:

```
+---------------+-------------------------------+
|  PyVarObject  |   ... ob_item ...             |    
+---------------+-------------------------------+
  tp_basicsize     tp_itemsize * ob_size
```

## 对象缓存池

tuple 的对象缓存池仅保存长度小于 PyTuple_MAXSAVESIZE 的 tuple, 而且对缓存池的大小也有限制.

```c
/* Speed optimization to avoid frequent malloc/free of small tuples */
// 优化 small tuple 的分配效率, 如果 tuple 的程度小于 PyTuple_MAXSAVESIZE, 那么将其缓存在 freelist.
#ifndef PyTuple_MAXSAVESIZE
#define PyTuple_MAXSAVESIZE     20  /* Largest tuple to save on free list */
#endif
#ifndef PyTuple_MAXFREELIST
#define PyTuple_MAXFREELIST  2000  /* Maximum number of tuples of each size to save */
#endif

#if PyTuple_MAXSAVESIZE > 0
/* Entries 1 up to PyTuple_MAXSAVESIZE are free lists, entry 0 is the empty
   tuple () of which at most one instance will be allocated.
*/
static PyTupleObject *free_list[PyTuple_MAXSAVESIZE];
static int numfree[PyTuple_MAXSAVESIZE];
#endif
```

使用对象缓存池的代码可以查看 PyTuple_New, PyTuple_alloc, PyTuple_dealloc.

## tuple 的创建过程

tuple 的创建过程: `PyTuple_New -> tuple_alloc -> PyObject_GC_NewVar -> _PyObject_GC_NewVar`

### PyTuple_New

```c
PyObject *
PyTuple_New(Py_ssize_t size)
{
    PyTupleObject *op;
    // 如果 size == 0, 那么直接返回 free_list[0].
    // 因为 tuple 是不可变对象, 所以可以这样优化空 tuple 的创建流程.
    // 所有的空 tuple 都是同一个对象, 就好像空字符串一样.
#if PyTuple_MAXSAVESIZE > 0
    if (size == 0 && free_list[0]) {
        op = free_list[0];
        Py_INCREF(op);
        return (PyObject *) op;
    }
#endif
    op = tuple_alloc(size);
    if (op == NULL) {
        return NULL;
    }
    for (Py_ssize_t i = 0; i < size; i++) {
        op->ob_item[i] = NULL;
    }
#if PyTuple_MAXSAVESIZE > 0
    if (size == 0) {
        free_list[0] = op;
        ++numfree[0];
        Py_INCREF(op);          /* extra INCREF so that this is never freed */
    }
#endif
    tuple_gc_track(op);
    return (PyObject *) op;
}
```

```c
static PyTupleObject *
tuple_alloc(Py_ssize_t size)
{
    PyTupleObject *op;
    if (size < 0) {
        PyErr_BadInternalCall();
        return NULL;
    }
#if PyTuple_MAXSAVESIZE > 0
    if (size < PyTuple_MAXSAVESIZE && (op = free_list[size]) != NULL) {
        assert(size != 0);
        // 下面这行代码类似于 free_list[size] = free_list[size].next
        free_list[size] = (PyTupleObject *) op->ob_item[0];
        numfree[size]--;
        /* Inline PyObject_InitVar */
#ifdef Py_TRACE_REFS
        Py_SIZE(op) = size;
        Py_TYPE(op) = &PyTuple_Type;
#endif
        _Py_NewReference((PyObject *)op);
    }
    else
#endif
    {
        /* Check for overflow */
        if ((size_t)size > ((size_t)PY_SSIZE_T_MAX - (sizeof(PyTupleObject) -
                    sizeof(PyObject *))) / sizeof(PyObject *)) {
            return (PyTupleObject *)PyErr_NoMemory();
        }
        op = PyObject_GC_NewVar(PyTupleObject, &PyTuple_Type, size);
        if (op == NULL)
            return NULL;
    }
    return op;
}
```

tuple_alloc 会先检查对象缓存池, 如果对象缓存池没有符合的数据, 那么调用 PyObject_GC_NewVar 分配内存.

### _PyObject_GC_NewVar

```c
// Modules/gcmodule.c
PyVarObject *
_PyObject_GC_NewVar(PyTypeObject *tp, Py_ssize_t nitems)
{
    size_t size;
    PyVarObject *op;

    if (nitems < 0) {
        PyErr_BadInternalCall();
        return NULL;
    }
    size = _PyObject_VAR_SIZE(tp, nitems);
    op = (PyVarObject *) _PyObject_GC_Malloc(size);
    if (op != NULL)
        // PyObject_INIT_VAR 负责设置 op->ob_size 和 op->ob_type
        op = PyObject_INIT_VAR(op, tp, nitems);
    return op;
}
```

_PyObject_GC_NewVar 负责分配 PyVarObject 的内存. _PyObject_VAR_SIZE 计算该对象占用的内存, 代码如下:

```c
#define _PyObject_VAR_SIZE(typeobj, nitems)     \
    _Py_SIZE_ROUND_UP((typeobj)->tp_basicsize + \
        (nitems)*(typeobj)->tp_itemsize,        \
        SIZEOF_VOID_P)
```        

可见 _PyObject_VAR_SIZE 对计算的值进行了向上取整, 向上取整是为了内存对齐. 下面是 Python 中定义的一些取整的宏:

```c
/* Below "a" is a power of 2. */
/* Round down size "n" to be a multiple of "a". */
#define _Py_SIZE_ROUND_DOWN(n, a) ((size_t)(n) & ~(size_t)((a) - 1))
/* Round up size "n" to be a multiple of "a". */
#define _Py_SIZE_ROUND_UP(n, a) (((size_t)(n) + \
        (size_t)((a) - 1)) & ~(size_t)((a) - 1))
/* Round pointer "p" down to the closest "a"-aligned address <= "p". */
#define _Py_ALIGN_DOWN(p, a) ((void *)((uintptr_t)(p) & ~(uintptr_t)((a) - 1)))
/* Round pointer "p" up to the closest "a"-aligned address >= "p". */
#define _Py_ALIGN_UP(p, a) ((void *)(((uintptr_t)(p) + \
        (uintptr_t)((a) - 1)) & ~(uintptr_t)((a) - 1)))
/* Check if pointer "p" is aligned to "a"-bytes boundary. */
#define _Py_IS_ALIGNED(p, a) (!((uintptr_t)(p) & (uintptr_t)((a) - 1)))
```

这些宏算是业界非常常见的写法.

分配好对象的内存后, 通过 PyObject_INIT_VAR 设置 op->ob_size 和 op->ob_type.

### _PyObject_GC_Malloc

```c
// Modules/gcmodule.c

static PyObject *
_PyObject_GC_Alloc(int use_calloc, size_t basicsize)
{
    PyThreadState *tstate = _PyThreadState_GET();
    GCState *gcstate = &tstate->interp->gc;
    if (basicsize > PY_SSIZE_T_MAX - sizeof(PyGC_Head)) {
        return _PyErr_NoMemory(tstate);
    }
    size_t size = sizeof(PyGC_Head) + basicsize;

    PyGC_Head *g;
    if (use_calloc) {
        g = (PyGC_Head *)PyObject_Calloc(1, size);
    }
    else {
        g = (PyGC_Head *)PyObject_Malloc(size);
    }
    if (g == NULL) {
        return _PyErr_NoMemory(tstate);
    }
    assert(((uintptr_t)g & 3) == 0);  // g must be aligned 4bytes boundary

    g->_gc_next = 0;
    g->_gc_prev = 0;
    gcstate->generations[0].count++; /* number of allocated GC objects */
    if (gcstate->generations[0].count > gcstate->generations[0].threshold &&
        gcstate->enabled &&
        gcstate->generations[0].threshold &&
        !gcstate->collecting &&
        !_PyErr_Occurred(tstate))
    {
        gcstate->collecting = 1;
        collect_generations(tstate);
        gcstate->collecting = 0;
    }
    PyObject *op = FROM_GC(g);
    return op;
}

PyObject *
_PyObject_GC_Malloc(size_t basicsize)
{
    return _PyObject_GC_Alloc(0, basicsize);
}
```

_PyObject_GC_Malloc 为对象分配内存的同时向对象添加 PyGC_Head. _PyObject_GC_Malloc 最终又是通过调用 PyObject_Malloc 分配内存, 而 PyObject_Malloc 最终在内存池中分配内存.


## 总结

通过阅读 tuple 的相关实现的代码, 可以了解 CPython 在内部是如何表示对象的(PyTupleObject, PyTuple_Type), 以及如何为对象分配内存.

## 其它

在看 tuple 的代码时, 发现了一个 tuple 所使用的哈希算法, xxhash. 

xxhash 的 [GitHub 地址](https://github.com/Cyan4973/xxHash).

