# 类型系统之 slot

slot 指的是 PyTypeObject(PyHeapTypeObject) 中的:

- tp_new
- tp_init
- tp_call
- tp_hash
- tp_repr
- tp_str
- tp_richcompare
- as_async
- as_number
- as_mapping
- as_sequence
- 等等

这些方法可以在 Python 层面进行重载(overload), 例如 tp_new 对应的 `__new__`, tp_init 对应的 `__init__`, as_number.nb_add 对应的 `__add__` 等等.

CPython 内部需要将 `__xxx__` 和 slot 关联起来, 这样当进行某些操作时可以找到用户定义的方法.

### slot table

slot table 其实是一个数组, 保存了 `__xxx__` 和 tp_xxx 之间的关系, 下面的注释说它们之间既可以是一对多也可以是多对一的关系.

```c
// Objects/typeobject.c
// 完整内容可以查看源码
/*
Table mapping __foo__ names to tp_foo offsets and slot_tp_foo wrapper functions.

The table is ordered by offsets relative to the 'PyHeapTypeObject' structure,
which incorporates the additional structures used for numbers, sequences and
mappings.  Note that multiple names may map to the same slot (e.g. __eq__,
__ne__ etc. all map to tp_richcompare) and one name may map to multiple slots
(e.g. __str__ affects tp_str as well as tp_repr). The table is terminated with
an all-zero entry.  (This table is further initialized in
_PyTypes_InitSlotDefs().)
*/
typedef struct wrapperbase slotdef;

#define TPSLOT(NAME, SLOT, FUNCTION, WRAPPER, DOC) \
    {NAME, offsetof(PyTypeObject, SLOT), (void *)(FUNCTION), WRAPPER, \
     PyDoc_STR(DOC)}
#define FLSLOT(NAME, SLOT, FUNCTION, WRAPPER, DOC, FLAGS) \
    {NAME, offsetof(PyTypeObject, SLOT), (void *)(FUNCTION), WRAPPER, \
     PyDoc_STR(DOC), FLAGS}
#define ETSLOT(NAME, SLOT, FUNCTION, WRAPPER, DOC) \
    {NAME, offsetof(PyHeapTypeObject, SLOT), (void *)(FUNCTION), WRAPPER, \
     PyDoc_STR(DOC)}

static slotdef slotdefs[] = {
    TPSLOT("__getattribute__", tp_getattr, NULL, NULL, ""),
    TPSLOT("__getattr__", tp_getattr, NULL, NULL, ""),
    TPSLOT("__setattr__", tp_setattr, NULL, NULL, ""),
    TPSLOT("__delattr__", tp_setattr, NULL, NULL, ""),
    TPSLOT("__repr__", tp_repr, slot_tp_repr, wrap_unaryfunc,
           "__repr__($self, /)\n--\n\nReturn repr(self)."),
    TPSLOT("__hash__", tp_hash, slot_tp_hash, wrap_hashfunc,
           "__hash__($self, /)\n--\n\nReturn hash(self)."),
    FLSLOT("__call__", tp_call, slot_tp_call, (wrapperfunc)(void(*)(void))wrap_call,
           "__call__($self, /, *args, **kwargs)\n--\n\nCall self as a function.",
           PyWrapperFlag_KEYWORDS),
    TPSLOT("__str__", tp_str, slot_tp_str, wrap_unaryfunc,
           "__str__($self, /)\n--\n\nReturn str(self)."),
    {NULL}
};
```

和 slotdefs 相关的两个最重要的操作是: add_operators 和 fixup_slot_dispatchers.

### 初始化 slotdefs 数组

主要任务就是设置 slotdef.name_strobj.

```c
static int slotdefs_initialized = 0;
/* Initialize the slotdefs table by adding interned string objects for the
   names. */
PyStatus
_PyTypes_InitSlotDefs(void)
{
    if (slotdefs_initialized) {
        return _PyStatus_OK();
    }

    for (slotdef *p = slotdefs; p->name; p++) {
        /* Slots must be ordered by their offset in the PyHeapTypeObject. */
        assert(!p[1].name || p->offset <= p[1].offset);
#ifdef INTERN_NAME_STRINGS
        p->name_strobj = PyUnicode_InternFromString(p->name);
        if (!p->name_strobj || !PyUnicode_CHECK_INTERNED(p->name_strobj)) {
            return _PyStatus_NO_MEMORY();
        }
#else
        p->name_strobj = PyUnicode_FromString(p->name);
        if (!p->name_strobj) {
            return _PyStatus_NO_MEMORY();
        }
#endif
    }
    slotdefs_initialized = 1;
    return _PyStatus_OK();
}
```

