# code 对象

```c
struct PyCodeObject {
    PyObject_HEAD
    int co_argcount;            /* #arguments, except *args */
    int co_posonlyargcount;     /* #positional only arguments */
    int co_kwonlyargcount;      /* #keyword only arguments */
    int co_nlocals;             /* #local variables */
    int co_stacksize;           /* #entries needed for evaluation stack */
    int co_flags;               /* CO_..., see below */
    int co_firstlineno;         /* first source line number */
    PyObject *co_code;          /* instruction opcodes */
    PyObject *co_consts;        /* list (constants used) */
    PyObject *co_names;         /* list of strings (names used) */
    PyObject *co_varnames;      /* tuple of strings (local variable names) */
    PyObject *co_freevars;      /* tuple of strings (free variable names) */
    PyObject *co_cellvars;      /* tuple of strings (cell variable names) */
    /* The rest aren't used in either hash or comparisons, except for co_name,
       used in both. This is done to preserve the name and line number
       for tracebacks and debuggers; otherwise, constant de-duplication
       would collapse identical functions/lambdas defined on different lines.
    */
    Py_ssize_t *co_cell2arg;    /* Maps cell vars which are arguments. */
    PyObject *co_filename;      /* unicode (where it was loaded from) */
    PyObject *co_name;          /* unicode (name, for reference) */
    PyObject *co_lnotab;        /* string (encoding addr<->lineno mapping) See
                                   Objects/lnotab_notes.txt for details. */
    void *co_zombieframe;       /* for optimization only (see frameobject.c) */
    PyObject *co_weakreflist;   /* to support weakrefs to code objects */
    /* Scratch space for extra data relating to the code object.
       Type is a void* to keep the format private in codeobject.c to force
       people to go through the proper APIs. */
    void *co_extra;

    /* Per opcodes just-in-time cache
     *
     * To reduce cache size, we use indirect mapping from opcode index to
     * cache object:
     *   cache = co_opcache[co_opcache_map[next_instr - first_instr] - 1]
     */

    // co_opcache_map is indexed by (next_instr - first_instr).
    //  * 0 means there is no cache for this opcode.
    //  * n > 0 means there is cache in co_opcache[n-1].
    unsigned char *co_opcache_map;
    _PyOpcache *co_opcache;
    int co_opcache_flag;  // used to determine when create a cache.
    unsigned char co_opcache_size;  // length of co_opcache.
};
```


## 字节码缓存(opcache)

注意到 PyCodeObject 对象中有一个 co_opcache 属性, 似乎支持字节码缓存, 查看了其它代码发现字节码缓存功能目前只支持 LOAD_GLOBALS.

字节码缓存的基本原理是保存字节码执行的结果, 当再次执行该字节码可以直接返回缓存的结果, 从而提高字节码的执行效率.

从定义 PyCodeObject 的结构体的代码注释中可以看出字节码缓存的实现原理, co_opcache_map 是一个 char 类型的数组, 索引是字节码的偏移量(`offset = next_instr - first_instr`), 如果 `co_opcache_map[offset]` 等于 0 说明该字节码没有缓存, 如果大于 0, 说明该字节码的缓存保存在 `co_opcache[co_opcache_map[offset]]`.

co_opcache 是一个 _PyOpcache 类型的数组, 代码如下:

```c
typedef struct {
    PyObject *ptr;  /* Cached pointer (borrowed reference) */
    uint64_t globals_ver;  /* ma_version of global dict */
    uint64_t builtins_ver; /* ma_version of builtin dict */
} _PyOpcache_LoadGlobal;

struct _PyOpcache {
    union {
        _PyOpcache_LoadGlobal lg;
    } u;
    char optimized;
};
```

`_PyOpcache_LoadGlobal.ptr` 指向缓存的数据, `_PyOpcache_LoadGlobal.globals_ver` 表示缓存数据时 globals(全局变量字典) 的版本, `_PyOpcache_LoadGlobal.builtins_ver` 表示缓存数据时 builtins 的版本. 

字典类型内部有一个版本字段 `ma_version_tag`, 每次字典被修改时, 都会增加版本字段. 代码如下:

```c
/*Global counter used to set ma_version_tag field of dictionary.
 * It is incremented each time that a dictionary is created and each
 * time that a dictionary is modified. */
static uint64_t pydict_global_version = 0;

#define DICT_NEXT_VERSION() (++pydict_global_version)
```

关于 `ma_version_tag` 的更多信息可以查看 [PEP 509 -- Add a private version to dict](https://www.python.org/dev/peps/pep-0509/).

当执行 `LOAD_GLOBAL` 时, 如果缓存存在并且缓存的版本号和当前版本号一致, 那么直接返回缓存的数据.

### 初始化 opcache

```c
int
_PyCode_InitOpcache(PyCodeObject *co)
{
    Py_ssize_t co_size = PyBytes_Size(co->co_code) / sizeof(_Py_CODEUNIT);
    co->co_opcache_map = (unsigned char *)PyMem_Calloc(co_size, 1);
    if (co->co_opcache_map == NULL) {
        return -1;
    }

    _Py_CODEUNIT *opcodes = (_Py_CODEUNIT*)PyBytes_AS_STRING(co->co_code);
    Py_ssize_t opts = 0;

    for (Py_ssize_t i = 0; i < co_size;) {
        unsigned char opcode = _Py_OPCODE(opcodes[i]);
        i++;  // 'i' is now aligned to (next_instr - first_instr)

        // TODO: LOAD_METHOD, LOAD_ATTR
        if (opcode == LOAD_GLOBAL) {
            opts++;
            co->co_opcache_map[i] = (unsigned char)opts;
            if (opts > 254) {
                break;
            }
        }
    }

    if (opts) {
        co->co_opcache = (_PyOpcache *)PyMem_Calloc(opts, sizeof(_PyOpcache));
        if (co->co_opcache == NULL) {
            PyMem_FREE(co->co_opcache_map);
            return -1;
        }
    }
    else {
        PyMem_FREE(co->co_opcache_map);
        co->co_opcache_map = NULL;
        co->co_opcache = NULL;
    }

    co->co_opcache_size = (unsigned char)opts;
    return 0;
}
```

### LOAD_GLOBAL 检查 opcache

```c
case TARGET(LOAD_GLOBAL): {
    PyObject *name;
    PyObject *v;
    if (PyDict_CheckExact(f->f_globals)
        && PyDict_CheckExact(f->f_builtins))
    {
        OPCACHE_CHECK();
        if (co_opcache != NULL && co_opcache->optimized > 0) {
            _PyOpcache_LoadGlobal *lg = &co_opcache->u.lg;

            if (lg->globals_ver ==
                    ((PyDictObject *)f->f_globals)->ma_version_tag
                && lg->builtins_ver ==
                    ((PyDictObject *)f->f_builtins)->ma_version_tag)
            {
                PyObject *ptr = lg->ptr;
                OPCACHE_STAT_GLOBAL_HIT();
                assert(ptr != NULL);
                Py_INCREF(ptr);
                PUSH(ptr);
                DISPATCH();
            }
        }

        name = GETITEM(names, oparg);
        v = _PyDict_LoadGlobal((PyDictObject *)f->f_globals,
                                (PyDictObject *)f->f_builtins,
                                name);
        if (v == NULL) {
            if (!_PyErr_OCCURRED()) {
                /* _PyDict_LoadGlobal() returns NULL without raising
                  * an exception if the key doesn't exist */
                format_exc_check_arg(tstate, PyExc_NameError,
                                      NAME_ERROR_MSG, name);
            }
            goto error;
        }

        if (co_opcache != NULL) {
            _PyOpcache_LoadGlobal *lg = &co_opcache->u.lg;

            if (co_opcache->optimized == 0) {
                /* Wasn't optimized before. */
                OPCACHE_STAT_GLOBAL_OPT();
            } else {
                OPCACHE_STAT_GLOBAL_MISS();
            }

            co_opcache->optimized = 1;
            lg->globals_ver =
                ((PyDictObject *)f->f_globals)->ma_version_tag;
            lg->builtins_ver =
                ((PyDictObject *)f->f_builtins)->ma_version_tag;
            lg->ptr = v; /* borrowed */
        }

        Py_INCREF(v);
    }
```

网上搜 "Python opcache" 发现都是关于 PHP 的, 唯一比较有用的信息是一个 [issue](https://bugs.python.org/issue26219). 这个 issue 在 2016 年提出, 2019 年才合并到 python 3.8. 到目前为止只支持 LOAD_GLOBAL, 未来应该会支持 LOAD_ATTR 和 LOAD_METHOD.

突然想到一个手动优化读取全局变量的性能的方法, 在函数内使用一个局部变量保存全局变量的引用, 然后在之后代码都使用该局部变量. 这招对于比较长的属性访问也有帮助, 例如 `foo = obj.a.b.c.d` 可以提高属性访问的速度. 

一个例子:

```py
class A:
    def __init__(self) -> None:
        self.a = 1

class B:
    def __init__(self) -> None:
        self.a = A()

class C:
    def __init__(self) -> None:
        self.b = B()

c = C()
print(c.b.a.a)
```

属性访问的字节码:

```
 15          48 LOAD_NAME                4 (print)
             50 LOAD_NAME                3 (c)
             52 LOAD_ATTR                5 (b)
             54 LOAD_ATTR                6 (a)
             56 LOAD_ATTR                6 (a)
             58 CALL_FUNCTION            1
```




