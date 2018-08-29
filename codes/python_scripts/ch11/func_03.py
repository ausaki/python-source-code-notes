def f(a, b, *args, **kwargs):
    print a, b, args, kwargs

f(1, 2, 3, 4, c=1, d=2)