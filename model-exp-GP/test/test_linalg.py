import sys

import autograd
from autograd import numpy as np
from scipy import linalg, stats
import gvar

sys.path = ['.'] + sys.path
from lsqfitgp2 import _linalg

class DecompTestBase:
    
    @property
    def decompclass(self):
        raise NotImplementedError()
        
    def randsize(self):
        return np.random.randint(1, 20)
        
    def randsymmat(self, n=None):
        if not n:
            n = self.randsize()
        O = stats.ortho_group.rvs(n) if n > 1 else np.atleast_2d(1)
        eigvals = np.random.uniform(1e-2, 1e2, size=n)
        K = (O * eigvals) @ O.T
        assert np.allclose(K, K.T)
        return K
    
    def mat(self, s, n=None):
        if not n and not isinstance(s, np.numpy_boxes.ArrayBox):
            n = self.randsize()
        x = np.arange(n)
        return np.exp(-1/2 * (x[:, None] - x[None, :]) ** 2 / s ** 2)
    
    matjac = autograd.jacobian(mat, 1)
    
    def randvec(self, n=None):
        if not n:
            n = self.randsize()
        return np.random.randn(n)
    
    def randmat(self, m=None, n=None):
        if not m:
            m = self.randsize()
        if not n:
            n = self.randsize()
        return np.random.randn(m, n)
    
    def solve(self, K, b):
        return linalg.solve(K, b)
            
    def test_solve_vec(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            b = self.randvec(len(K))
            sol = self.solve(K, b)
            result = self.decompclass(K).solve(b)
            assert np.allclose(sol, result, rtol=1e-4)
    
    def test_solve_vec_jac(self):
        def fun(s, n, b):
            K = self.mat(s, n)
            return self.decompclass(K).solve(b)
        funjac = autograd.jacobian(fun)
        for n in range(1, 20):
            s = np.exp(np.random.uniform(-1, 1))
            K = self.mat(s, n)
            dK = self.matjac(s, n)
            b = self.randvec(n)
            sol = -self.solve(K.T, self.solve(K, dK).T).T @ b
            result = funjac(s, n, b)
            assert np.allclose(sol, result, rtol=1e-3)

    def test_solve_matrix(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            b = self.randmat(len(K))
            sol = self.solve(K, b)
            result = self.decompclass(K).solve(b)
            assert np.allclose(sol, result, rtol=1e-4)

    def test_solve_matrix_jac(self):
        def fun(s, n, b):
            K = self.mat(s, n)
            return self.decompclass(K).solve(b)
        funjac = autograd.jacobian(fun)
        for n in range(1, 20):
            s = np.exp(np.random.uniform(-1, 1))
            K = self.mat(s, n)
            dK = self.matjac(s, n)
            b = self.randmat(n)
            sol = -self.solve(K.T, self.solve(K, dK).T).T @ b
            result = funjac(s, n, b)
            assert np.allclose(sol, result, rtol=1e-3)

    def test_solve_matrix_jac_matrix(self):
        def fun(s, n, b, A):
            K = self.mat(s, n)
            return A @ self.decompclass(K).solve(b)
        funjac = autograd.jacobian(fun)
        for n in range(1, 20):
            s = np.exp(np.random.uniform(-1, 1))
            K = self.mat(s, n)
            dK = self.matjac(s, n)
            b = self.randmat(n)
            A = self.randmat(n).T
            sol = -A @ self.solve(K.T, self.solve(K, dK).T).T @ b
            result = funjac(s, n, b, A)
            assert np.allclose(sol, result, rtol=1e-3)

    def test_usolve_vec_gvar(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            mean = self.randvec(len(K))
            xcov = np.linspace(0, 3, len(K))
            cov = np.exp(-(xcov.reshape(-1, 1) - xcov.reshape(1, -1)) ** 2)
            b = gvar.gvar(mean, cov)
            invK = self.solve(K, np.eye(len(K)))
            sol = invK @ b
            result = self.decompclass(K).usolve(b)
            diff = result - sol
            
            diffmean = gvar.mean(diff)
            solcov = gvar.evalcov(gvar.svd(sol))
            q = diffmean @ linalg.solve(solcov, diffmean, assume_a='pos')
            assert np.allclose(q, 0, atol=1e-7)
            
            diffcov = gvar.evalcov(diff)
            solmax = np.max(linalg.eigvalsh(solcov))
            diffmax = np.max(linalg.eigvalsh(diffcov))
            assert np.allclose(diffmax / solmax, 0)
    
    def test_quad_vec(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            b = self.randvec(len(K))
            sol = b.T @ self.solve(K, b)
            result = self.decompclass(K).quad(b)
            assert np.allclose(sol, result)
    
    def test_quad_matrix(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            b = self.randmat(len(K))
            sol = b.T @ self.solve(K, b)
            result = self.decompclass(K).quad(b)
            assert np.allclose(sol, result)
    
    def test_quad_vec_grad(self):
        def fun(s, n, b):
            K = self.mat(s, n)
            return self.decompclass(K).quad(b)
        fungrad = autograd.jacobian(fun)
        for n in range(1, 20):
            s = np.exp(np.random.uniform(-1, 1))
            K = self.mat(s, n)
            dK = self.matjac(s, n)
            b = self.randvec(n)
            invKb = self.solve(K, b)
            sol = -invKb.T @ dK @ invKb
            result = fungrad(s, n, b)
            assert np.allclose(sol, result, rtol=1e-4)

    def test_logdet(self):
        for n in range(1, 20):
            K = self.randsymmat()
            sol = np.sum(np.log(linalg.eigvalsh(K)))
            result = self.decompclass(K).logdet()
            assert np.allclose(sol, result)
    
    def test_logdet_grad(self):
        def fun(s, n):
            K = self.mat(s, n)
            return self.decompclass(K).logdet()
        fungrad = autograd.grad(fun)
        for n in range(1, 20):
            s = np.exp(np.random.uniform(-1, 1))
            K = self.mat(s, n)
            dK = self.matjac(s, n)
            sol = np.trace(self.solve(K, dK))
            result = fungrad(s, n)
            assert np.allclose(sol, result, rtol=1e-4)
    
    # TODO test second derivatives

class TestDiag(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.Diag

class TestEigCutFullRank(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.EigCutFullRank

class TestEigCutLowRank(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.EigCutLowRank

class TestChol(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.Chol

class TestCholMaxEig(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.CholMaxEig

class TestCholGersh(DecompTestBase):
    
    @property
    def decompclass(self):
        return _linalg.CholGersh

def _noautograd(x):
    if isinstance(x, np.numpy_boxes.ArrayBox):
        return x._value
    else:
        return x

class TestReduceRank(DecompTestBase):
    
    @property
    def decompclass(self):
        return lambda K: _linalg.ReduceRank(K, rank=self._rank)
    
    def solve(self, K, b):
        invK, rank = linalg.pinv(K, return_rank=True)
        assert rank == self._rank
        return invK @ b
    
    def randsymmat(self, n=None):
        if not n:
            n = self.randsize()
        self._rank = np.random.randint(1, n + 1)
        O = stats.ortho_group.rvs(n) if n > 1 else np.atleast_2d(1)
        eigvals = np.random.uniform(1e-2, 1e2, size=self._rank)
        O = O[:, :self._rank]
        K = (O * eigvals) @ O.T
        assert np.allclose(K, K.T)
        return K
    
    def mat(self, s, n=None):
        if not isinstance(s, np.numpy_boxes.ArrayBox):
            if not n:
                n = self.randsize()
            self._rank = np.random.randint(1, n + 1)
        x = np.arange(n)
        x[:n - self._rank + 1] = x[0]
        return np.exp(-1/2 * (x[:, None] - x[None, :]) ** 2 / s ** 2)
    
    matjac = autograd.jacobian(mat, 1)
        
    def test_logdet(self):
        for n in range(1, 20):
            K = self.randsymmat(n)
            sol = np.sum(np.log(np.sort(linalg.eigvalsh(K))[-self._rank:]))
            result = self.decompclass(K).logdet()
            assert np.allclose(sol, result)

def test_solve_triangular():
    for n in range(1, 20):
        for ndim in range(3):
            for lower in [True, False]:
                tri = np.tril if lower else np.triu
                A = tri(np.random.randn(n, n))
                diag = np.sqrt(np.sum(np.random.randn(n, 2) ** 2, axis=-1) / 2)
                A[np.diag_indices(n)] = diag
                shape = np.random.randint(1, 4, size=ndim)
                B = np.random.randn(n, *shape)
                check_solve_triangular(A, B, lower)

def check_solve_triangular(A, B, lower):
    # scipy.linalg.solve_triangular is documented to work with b 1- or
    # 2-dimensional, but it does not raise an error with b n-dimensional and
    # the result does not satisfy sum_i A[j,i] * x[i,...] = B[j,...].
    # TODO understand what solve_triangular does and file a bug report to scipy
    x1 = linalg.solve_triangular(A, B.reshape(B.shape[0], -1), lower=lower).reshape(B.shape)
    assert np.allclose(np.tensordot(A, x1, 1), B)
    x2 = _linalg.solve_triangular(A, B, lower=lower)
    assert np.allclose(x1, x2)
