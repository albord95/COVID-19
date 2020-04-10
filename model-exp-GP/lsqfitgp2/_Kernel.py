from __future__ import division

import autograd
from autograd import numpy as np
from autograd.builtins import isinstance

from . import _array

__all__ = [
    'Kernel',
    'IsotropicKernel',
    'kernel',
    'isotropickernel'
]

def _apply2fields(transf, x):
    if x.dtype.names is not None:
        x = _array.StructuredArray(x)
        for name in x.dtype.names:
            x[name] = transf(x[name])
        return x
    else:
        return transf(x)

def _asarray(x):
    if isinstance(x, _array.StructuredArray):
        return x
    else:
        return np.array(x, copy=False)

def _effectivearray(x):
    if isinstance(x, _array.StructuredArray):
        return x[x.dtype.names[0]]
    else:
        return x

def _asfloat(x):
    return np.array(x, copy=False, dtype=float)

class Kernel:
    """
    
    Base class for objects representing covariance kernels. A Kernel object
    is callable, the signature is obj(x, y). Kernel objects can be summed and
    multiplied between them and with scalars, or raised to power with a scalar
    exponent.
    
    This class can be used directly by passing a callable at initialization, or
    it can be subclassed. Subclasses need to assign the member `_kernel` with a
    callable that will be called when the Kernel object is called. `_kernel`
    will be called with two arguments x, y that are two broadcastable numpy
    arrays. It must return Cov[f(x), f(y)] where `f` is the gaussian process.
    
    If `x` and `y` are structured arrays, they represent multidimensional
    input. Kernels can be specified to act only on a field of `x` and `y` or
    on all of them.
        
    The decorator `@kernel` can be used to quickly make subclasses.
    
    Methods
    -------
    diff :
        Derivatives of the kernel.
    
    """
    
    def __init__(self, kernel, *, dim=None, loc=0, scale=1, forcebroadcast=False, forcekron=False, **kw):
        """
        
        Initialize the object with callable `kernel`.
        
        Parameters
        ----------
        kernel : callable
            A function with signature `kernel(x, y)` where x and y are two
            broadcastable numpy arrays which computes the covariance of f(x)
            with f(y) where f is the gaussian process.
        dim : None or str
            When the input arrays are structured arrays, if dim=None the kernel
            will operate on all fields, i.e. it will be passed the whole
            arrays. If `dim` is a string, `kernel` will see only the arrays for
            the field `dim`. If `dim` is a string and the array is not
            structured, an exception is raised.
        loc, scale : scalars
            The inputs to `kernel` are transformed as (x - loc) / scale.
        forcebroadcast : bool
            If True, the inputs to `kernel` will always have the same shape.
        forcekron : bool
            If True, when calling `kernel`, if `x` and `y` are structured
            arrays, i.e. if they represent multidimensional input, `kernel` is
            invoked separately for each dimension, and the result is the
            product. Default False. If `dim` is specified, `forcekron` will
            have no effect.
        **kw :
            Other keyword arguments are passed to `kernel`: kernel(x, y, **kw).
        
        """
        assert isinstance(dim, (str, type(None)))
        assert np.isscalar(scale)
        assert np.isfinite(scale)
        assert scale > 0
        assert np.isscalar(loc)
        assert np.isfinite(loc)
        self._forcebroadcast = bool(forcebroadcast)
        forcekron = bool(forcekron)
        
        transf = lambda x: x
        
        if isinstance(dim, str):
            def transf(x):
                if x.dtype.names is not None:
                    return x[dim]
                else:
                    raise ValueError('kernel called on non-structured array but dim="{}"'.format(dim))
        
        if loc != 0:
            transf1 = transf
            transf = lambda x: _apply2fields(lambda x: x - loc, transf1(x))
        
        if scale != 1:
            transf2 = transf
            transf = lambda x: _apply2fields(lambda x: x / scale, transf2(x))
                
        if dim is None and forcekron:
            def _kernel(x, y):
                x = transf(x)
                y = transf(y)
                if x.dtype.names is not None:
                    return np.prod(np.stack([
                        kernel(x[f], y[f], **kw)
                        for f in x.dtype.names
                    ]), axis=0)
                else:
                    return kernel(x, y, **kw)
        else:
            _kernel = lambda x, y: kernel(transf(x), transf(y), **kw)
        
        self._kernel = _kernel
    
    def __call__(self, x, y):
        x = _asarray(x)
        y = _asarray(y)
        assert x.dtype == y.dtype
        shape = np.broadcast(_effectivearray(x), _effectivearray(y)).shape
        if self._forcebroadcast:
            x, y = np.broadcast_arrays(x, y)
        result = self._kernel(x, y)
        assert isinstance(result, (np.ndarray, np.number))
        assert np.issubdtype(result.dtype, np.number)
        assert result.shape == shape
        return result
    
    def __add__(self, value):
        if isinstance(value, Kernel):
            return Kernel(lambda x, y: self._kernel(x, y) + value._kernel(x, y))
        elif np.isscalar(value):
            assert np.isfinite(value)
            return Kernel(lambda x, y: self._kernel(x, y) + value)
        else:
            return NotImplemented
    
    __radd__ = __add__
    
    def __mul__(self, value):
        if isinstance(value, Kernel):
            return Kernel(lambda x, y: self._kernel(x, y) * value._kernel(x, y))
        elif np.isscalar(value):
            assert np.isfinite(value)
            assert value >= 0
            return Kernel(lambda x, y: value * self._kernel(x, y))
        else:
            return NotImplemented
    
    __rmul__ = __mul__
    
    def __pow__(self, value):
        if np.isscalar(value):
            assert np.isfinite(value)
            assert value >= 0
            return Kernel(lambda x, y: self._kernel(x, y) ** value)
        else:
            return NotImplemented
    
    def diff(self, xorder=0, yorder=0, xdim=None, ydim=None):
        """
        
        Return a Kernel object that computes the derivatives of this kernel.
        The derivatives are computed automatically with `autograd`. If `xorder`
        and `yorder` are 0, this is a no-op and returns the object itself.
        
        Parameters
        ----------
        xorder, yorder : int
            How many times the kernel is derived w.r.t the first and second
            arguments respectively.
        xdim, ydim : None or str
            When the inputs are structured arrays, indicate which field to
            derivate.
        
        Returns
        -------
        diffkernel : Kernel
            Another Kernel object representing the derivatives of this one.
        """
        for order in xorder, yorder:
            if not isinstance(order, (int, np.integer)) or order < 0:
                raise ValueError('derivative orders must be nonnegative integers')
        for dim in xdim, ydim:
            assert isinstance(dim, (str, type(None)))
        
        if xorder == yorder == 0:
            return self
        
        kernel = self._kernel
        def fun(x, y):
            if x.dtype.names is not None:
                for order, dim, z in zip((xorder, yorder), (xdim, ydim), (x, y)):
                    if order and dim is None:
                        raise ValueError('can not differentiate w.r.t structured input ({}) if dim not specified'.format(', '.join(z.dtype.names)))
                    if order and dim not in z.dtype.names:
                        raise ValueError('differentiation dimension "{}" missing in fields ({})'.format(dim, ', '.join(z.dtype.names)))
                if xorder:
                    x = _array.StructuredArray(x)
                if yorder:
                    y = _array.StructuredArray(y)
                def f(a, b):
                    if xorder:
                        x[xdim] = a
                    if yorder:
                        y[ydim] = b
                    return kernel(x, y)
            else:
                f = kernel
            
            for _ in range(xorder):
                f = autograd.elementwise_grad(f, 0)
            for _ in range(yorder):
                f = autograd.elementwise_grad(f, 1)
            
            if x.dtype.names is not None:
                X = _asfloat(x[xdim]) if xorder else None
                Y = _asfloat(y[ydim]) if yorder else None
                return f(X, Y)
            else:
                return f(_asfloat(x) if xorder else x, _asfloat(y) if yorder else y)
        
        return Kernel(fun, forcebroadcast=True)
            
class IsotropicKernel(Kernel):
    """
    
    Subclass of `Kernel` that represents isotropic kernels, i.e. the result
    only depends on a distance defined between points. The decorator for
    making subclasses is `isotropickernel`.
    
    """
    
    def __init__(self, kernel, *, input='squared', **kw):
        """
        
        Parameters
        ----------
        kernel : callable
            A function taking one argument `r2` which is the squared distance
            between x and y, plus optionally keyword arguments. `r2` is a 1D
            numpy array.
        input : str
            See "input options" below.
        **kw :
            Other keyword arguments are passed to the `Kernel` init.
        
        Input options
        -------------
        squared :
            Pass the squared distance (default).
        soft :
            Pass the distance, but instead of 0 it yields a very small number.
        
        """
        allowed_input = ('squared', 'soft')
        if not (input in allowed_input):
            raise ValueError('input option `{}` not valid, must be one of {}'.format(input, allowed_input))
        
        def function(x, y, **kwargs):
            if x.dtype.names is not None:
                q = sum((x[f] - y[f]) ** 2 for f in x.dtype.names)
            else:
                q = (x - y) ** 2
            if input == 'soft':
                eps = np.finfo(x.dtype).eps
                q = np.sqrt(q + eps ** 2)
            return kernel(q, **kwargs)
        
        super().__init__(function, **kw)
    
def _makekernelsubclass(kernel, superclass, **prekw):
    assert issubclass(superclass, Kernel)
    
    supername = 'Specific' + superclass.__name__
    name = getattr(kernel, '__name__', supername)
    if name == '<lambda>':
        name = supername
    
    newclass = type(name, (superclass,), {})
    
    def __init__(self, **kw):
        kwargs = prekw.copy()
        kwargs.update(kw)
        return super(newclass, self).__init__(kernel, **kwargs)
    newclass.__init__ = __init__
    newclass.__doc__ = kernel.__doc__
    
    return newclass

def _kerneldecoratorimpl(cls, *args, **kw):
    functional = lambda kernel: _makekernelsubclass(kernel, cls, **kw)
    if len(args) == 0:
        return functional
    elif len(args) == 1:
        return functional(*args)
    else:
        raise ValueError(len(args))

def kernel(*args, **kw):
    """
    
    Decorator to convert a function to a subclass of `Kernel`. Use it like this:
    
    @kernel
    def MyKernel(x, y, cippa=1, lippa=42, ...):
        return ... # something computing Cov[f(x), f(y)]
    
    """
    return _kerneldecoratorimpl(Kernel, *args, **kw)

def isotropickernel(*args, **kw):
    """
    
    Decorator to convert a function to a subclass of `IsotropicKernel`. Use it
    like this:
    
    @isotropickernel
    def MyKernel(rsquared, cippa=1, lippa=42, ...):
        return ...
        # something computing Cov[f(x), f(y)] where rsquared = ||x - y||^2
    
    """
    return _kerneldecoratorimpl(IsotropicKernel, *args, **kw)