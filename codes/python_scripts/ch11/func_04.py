def f(a):
    v = 'value'
    def g():
        print v
    return g

g = f(1)
g()