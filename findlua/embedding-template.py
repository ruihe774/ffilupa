from {libname} import ffi
from ffilupa import embedding

@ffi.def_extern()
def _ffilupa_init(L):
    embedding.init(L, '{libname}'[19:])
