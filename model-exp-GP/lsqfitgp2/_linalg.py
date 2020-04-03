import numpy as np
from scipy import linalg
from scipy.sparse import linalg as slinalg

__doc__ = """

Decompositions of positive definite matrices. A decomposition object is
initialized with a matrix and then can solve linear systems for that matrix.

Classes
-------
Decomposition :
    Abstract base class.
SVD :
    Singular value decomposition.
SVDFullRank :
    SVD rounding up small singular values.
SVDLowRank :
    SVD removing small singular values.
LowRank :
    Partial diagonalization with higher eigenvalues only.
Chol :
    Cholesky decomposition.
CholMaxEig :
    Cholesky regularized using the maximum eigenvalue.
CholGersh :
    Cholesky regularized using an estimate of the maximum eigenvalue.

"""

class Decomposition:
    """
    Abstract base class for positive definite symmetric matrices decomposition.
    
    Methods
    -------
    solve
    usolve
    quad
    logdet
    
    """
    
    def __init__(self, K, overwrite=False):
        """
        Decompose matrix K.
        """
        raise NotImplementedError()
    
    def solve(self, b):
        """
        Solve the linear system K @ x = b.
        """
        raise NotImplementedError()
    
    def usolve(self, ub):
        """
        Solve the linear system K @ x = b where b is possibly an array of
        `gvar`s.
        """
        inv = self.solve(np.eye(len(ub)))
        return inv @ ub ### MATRIX INVERSION!!! BAD!!!
    
    def quad(self, b):
        """
        Compute the quadratic form b.T @ K**(-1) @ b.
        """
        return b.T @ self.solve(b)
    
    def logdet(self):
        """
        Compute log(det(K)).
        """
        raise NotImplementedError()

class SVD(Decomposition):
    """
    Singular value decomposition.
    """
    
    def __init__(self, K, overwrite=False):
        self._U, self._s, self._VT = linalg.svd(K, check_finite=False, overwrite_a=overwrite)
    
    def solve(self, b):
        return (self._VT.T / self._s) @ (self._U.T @ b)
    
    usolve = solve
    
    def logdet(self):
        return np.sum(np.log(self._s))
    
    def _eps(self, eps):
        s = self._s
        if eps is None:
            eps = len(s) * np.finfo(s.dtype).eps
        return eps * np.max(s)

class SVDFullRank(SVD):
    """
    Singular value decomposition. Singular values below `eps` are set to
    `eps`, where `eps` is relative to the largest singular value.
    """
    
    def __init__(self, K, eps=None, **kw):
        super().__init__(K, **kw)
        eps = self._eps(eps)
        self._s[self._s < eps] = eps
            
class SVDLowRank(SVD):
    """
    Singular value decomposition. Singular values below `eps` are removed,
    where `eps` is relative to the largest singular value.
    """
    
    def __init__(self, K, eps=None, **kw):
        super().__init__(K, **kw)
        eps = self._eps(eps)
        subset = slice(np.sum(self._s >= eps)) # s is decreasing
        self._U = self._U[:, subset]
        self._s = self._s[subset]
        self._VT = self._VT[subset, :]
        
class LowRank(Decomposition):
    """
    Keep only the first `rank` higher eigenmodes.
    """
    
    def __init__(self, K, rank=1, overwrite=None):
        self._w, self._V = slinalg.eigsh(K, k=rank, which='LM')
        
    def solve(self, b):
        return (self._V / self._w) @ (self._V.T @ b)
    
    usolve = solve
    
    def quad(self, b):
        VTb = self._V.T @ b
        return (VTb.T / self._w) @ VTb
    
    def logdet(self):
        return np.sum(np.log(self._w))

class Chol(Decomposition):
    """
    Cholesky decomposition.
    """
    
    def __init__(self, K, overwrite=False):
        self._L = linalg.cholesky(K, lower=True, check_finite=False, overwrite_a=overwrite)
    
    def solve(self, b):
        invLb = linalg.solve_triangular(self._L, b, lower=True)
        return linalg.solve_triangular(self._L.T, invLb, lower=False)
    
    def usolve(self, b):
        invL = linalg.solve_triangular(self._L, np.eye(len(self._L)), lower=True)
        return (invL.T @ invL) @ b ### MATRIX INVERSION!!! BAD!!!
    
    def quad(self, b):
        invLb = linalg.solve_triangular(self._L, b, lower=True)
        return invLb.T @ invLb
    
    def logdet(self):
        return 2 * np.sum(np.log(np.diag(self._L)))

class CholMaxEig(Chol):
    """
    Cholesky decomposition. The matrix is corrected for numerical roundoff
    by adding to the diagonal a small number relative to the maximum eigenvalue.
    `epsfactor` multiplies this number.
    """
    
    def __init__(self, K, eps=None, **kw):
        w = slinalg.eigsh(K, k=1, which='LM', return_eigenvectors=False)
        if not eps:
            eps = len(K) * np.finfo(K.dtype).eps
        super().__init__(K + np.diag(np.full(len(K), eps * w[0])), **kw)


class CholGersh(Chol):
    """
    Cholesky decomposition. The matrix is corrected for numerical roundoff
    by adding to the diagonal a small number relative to the maximum eigenvalue.
    `epsfactor` multiplies this number. The maximum eigenvalue is estimated
    with the Gershgorin theorem.
    """
    
    def __init__(self, K, eps=None, **kw):
        maxeigv = _gershgorin_eigval_bound(K)
        if not eps:
            eps = len(K) * np.finfo(K.dtype).eps
        super().__init__(K + np.diag(np.full(len(K), eps * maxeigv)), **kw)

def _gershgorin_eigval_bound(K):
    return np.max(np.sum(np.abs(K), axis=1))
