# 类型系统之 MRO

```py
class A:
    pass

class B:
    pass

class C(A, B):
    pass

class D(B, A):
    pass

class E(C, D):
    pass
```

执行上面的代码会报错: 

```
Traceback (most recent call last):
  File "/home/vvv/Workspace/cpython/mydemo/class_demo.py", line 16, in <module>
    class E(C, D):
TypeError: Cannot create a consistent method resolution
order (MRO) for bases A, B
```

## C3 算法

算法实现

在 CPython 中对应的算法实现是 `Objects/typeobject.c` 中的 `mro_implementation` 函数. 先看 [参考](#参考)然后再看算法实现更容易理解.

## 参考

- [https://www.python.org/download/releases/2.3/mro/](https://www.python.org/download/releases/2.3/mro/)

- [https://en.wikipedia.org/wiki/C3_linearization](https://en.wikipedia.org/wiki/C3_linearization)