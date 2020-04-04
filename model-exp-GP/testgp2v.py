import lsqfitgp2 as lgp
import autograd
from autograd import numpy as np

def fun(params):
    scale = params[0]
    gp = lgp.GP(lgp.ExpQuad(scale=scale))
    x = np.arange(10)
    gp.addx(x)
    y = np.sin(x)
    return gp.marginal_likelihood(y)

fungrad = autograd.grad(fun)

params = np.array([3], dtype=float)
print(fungrad(params))
