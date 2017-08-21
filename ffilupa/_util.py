from __future__ import absolute_import, unicode_literals
import six
import ffilupa


def py_object_callback(err_msg):
    def make_callback(func):
        @six.wraps(func)
        def callback(L, *args):
            py_obj = ffilupa.unwrap_lua_object(L, 1)
            if not py_obj:
                return -1
            try:
                runtime = ffilupa.lua.ffi.from_handle(py_obj[0].runtime)
                return func(runtime, L, py_obj, *args)
            except:
                try:
                    runtime.store_raised_exception(L, err_msg)
                finally:
                    return -1
        return callback
    return make_callback


__all__ = ()
