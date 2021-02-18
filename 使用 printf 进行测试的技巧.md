# 使用 printf 进行测试的技巧

如果直接在代码中使用 printf 输出测试信息, 那么在编译时会产生大量 printf 的信息. 更好的做法是使用一个 debug 变量来判断是否要进行测试.

我的做法是:

```c
int debug = PySys_GetObject('_debug') != NULL ? 1 : 0;

if(debug){
    // 输出信息
}
```

在 Python 代码中使用 `sys._debug = 1` 来设置 `_debug` 属性.

当然这个方法有局限性, 需要执行 Python 代码, 在 CPython 还没有真正执行 Python 代码时, debug 变量一直是 0.

其它方法:

- 向 CPython 添加一个命令行参数.

- 环境变量.

打印对象信息: `_PyObject_Dump`.

