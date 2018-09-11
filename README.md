# 《Python 源码剖析》学习笔记

> 《Python 源码剖析》
> 作者：陈儒 Robert Chen
> 出版年份：2008 年
> Python 版本：2.5

在阅读《Python 源码剖析》的过程中记录的一些笔记，不是特别详细，简单记录了一些关键的地方，方便以后查看。

## 编译代码

使用 Docker 编译 Python 源代码，使用说明参考 [Docker 使用说明](docker.md)。

## 源代码

在阅读《Python 源码剖析》过程中，为了验证一些想法，对 Python2.5的源代码进行了不少修改。修改过的代码在[这里](https://github.com/ausaki/python25)。

master 分支是原始代码。

每个 chxx 分支对应书中相应的章节，基于 master 分支修改而来。

## 其它资源

- [作者在 CSDN 的博客](https://blog.csdn.net/balabalamerobert)(不再更新)。

- [Extending and Embedding the Python Interpreter](https://docs.python.org/2.7/extending/index.html)

    扩展和嵌入 Python 解析器，介绍了如何用 C/C++ 编写 Python 的扩展模块，如何在其它语言中嵌入 Python 解释器。

- [C API](https://docs.python.org/2.7/c-api/index.html)

    详细介绍了 Python 内部的 C API。

- [Python Developer’s Guide](https://devguide.python.org/)

    Python 开发者指南。



## 目录

- 第一部分

    - [ch01 - Pyhton 对象初探](ch01.md)
    - [ch02 - Pyhton 中的整数对象](ch02.md)
    - [ch03 - Pyhton 中的字符串对象](ch03.md)
    - [ch04 - Python 中的 List 对象](ch04.md)
    - [ch05 - Python 中的 Dict 对象](ch05.md)
    - [ch06 - 最简单的Python模拟——Small Python](ch06.md)

- 第二部分

    - [ch07 - Python的编译结果——Code对象与pyc文件](ch07.md)
    - [ch08 - Python 虚拟机框架](ch08.md)
    - [ch09 - Python虚拟机中的一般表达式](ch09.md)
    - [ch010 - Python虚拟机中的控制流](ch10.md)
    - [ch011 - Python虚拟机中的函数机制](ch11.md)
    - [ch012 - Python虚拟机中的类机制](ch12.md)
    - [ch013 - Python运行环境初始化](ch13.md)
    - [ch014 - Python模块的动态加载机制](ch14.md)
    - [ch015 - Python多线程机制](ch15.md)
    - [ch016 - Python的内存管理机制](ch16.md)

