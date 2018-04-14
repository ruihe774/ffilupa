from {libname} import ffi

@ffi.def_extern()
def _ffilupa_init(L, path):
    import os
    path = os.fsdecode(ffi.string(path))
    import sys
    sys.path.insert(0, path)
    from ffilupa import embedding
    embedding.init(L, '{libname}'[19:])
