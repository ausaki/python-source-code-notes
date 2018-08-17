# 《Python 源码剖析》学习笔记

> 我看的《Python 源码剖析》是 2008 年出版的，Python 版本是 2.5。

在阅读《Python 源码剖析》的过程中记录的一些笔记，不是特别详细，简单记录了一些关键的地方，方便以后查看。

## 编译代码

使用 Docker 编译 Python 源代码，使用说明参考 [Docker 使用说明](docker.md)。

## 源代码

在阅读《Python 源码剖析》过程中，为了验证一些想法，对 Python2.5的源代码进行了不少修改。修改过的代码在[这里](https://github.com/ausaki/python25)。

master 分支是原始代码。

每个 chxx 分支对应书中相应的章节，基于 master 分支修改而来。


## 目录

- [ch01 - Pyhton 对象初探](ch01.md)
- [ch02 - Pyhton 中的整数对象](ch02.md)
- [ch03 - Pyhton 中的字符串对象](ch03.md)
- [ch04 - Python 中的 List 对象](ch04.md)

