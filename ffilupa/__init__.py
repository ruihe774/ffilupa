import pkg_resources

__version__ = pkg_resources.get_distribution('ffilupa').version

from .runtime import *
from .exception import *
from .protocol import *
from .compat import *
from .lualibs import *

def _gen_all():
    global __all__
    from . import runtime as _rt
    from . import exception as _exc
    from . import protocol as _prc
    from . import compat as _cp
    from . import lualibs as _ll
    __all__ = _rt.__all__ + _exc.__all__ + _prc.__all__ + _cp.__all__ + _ll.__all__
_gen_all()
