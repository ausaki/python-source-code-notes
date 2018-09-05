# -*- coding: utf-8 -*-
""" 测试类的创建流程
"""
class MyTestClass(object):
    def __init__(self, name):
        self.name = name
    
    def f(self):
        print self.name
    
    def g(self, a):
        print a

c = MyTestClass('jack')
c.f()