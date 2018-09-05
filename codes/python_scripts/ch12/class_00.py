class A(object):
    name = 'Python'
    def __init__(self):
        print 'A::__init__'

    def f(self):
        print 'A::f'

    def g(self, aValue):
        self.value = aValue
        print self.value

a = A()
a.f()
a.g(10)