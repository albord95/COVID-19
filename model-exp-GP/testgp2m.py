import lsqfitgp2 as lgp
from matplotlib import pyplot as plt
import numpy as np
import gvar
from scipy import optimize

xdata = np.linspace(0, 10, 10)
xpred = np.linspace(-15, 25, 500)
y = np.sin(xdata)

def makegp(par):
    scale = np.exp(par[0])
    nu = np.exp(par[1])
    return lgp.GP(lgp.Matern(scale=scale, nu=nu))

def fun(par):
    gp = makegp(par)
    gp.addx(xdata)
    return -gp.marginal_likelihood(y)

result = optimize.minimize(fun, np.log([5, 5]), method='Nelder-Mead')
print(result)

gp = makegp(result.x)
gp.addx(xdata, 'data')
gp.addx(xpred, 'pred')

m, cov = gp.predfromdata({'data': y}, 'pred', raw=True)
s = np.sqrt(np.diag(cov))

fig = plt.figure('testgp2m')
fig.clf()
ax = fig.subplots(1, 1)

patch = ax.fill_between(xpred, m - s, m + s, label='pred', alpha=0.5)
color = patch.get_facecolor()[0]
simulated_lines = np.random.multivariate_normal(m, cov, size=10)
ax.plot(xpred, simulated_lines.T, '-', color=color)
ax.plot(xdata, y, 'k.', label='data')
ax.legend(loc='best')

fig.show()
