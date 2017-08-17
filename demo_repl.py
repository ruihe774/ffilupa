#!/usr/bin/env python

import sys
import readline
import six
import ffilupa

lua = ffilupa.lua
ll = lua.lib
lf = lua.ffi


class LuaREPL(object):
    def __init__(self):
        self.lua_runtime = ffilupa.LuaRuntime()

    PROMPT1 = '>>> '
    PROMPT2 = '... '
    EOFMARK	= b'<eof>'

    def readline(self, firstline):
        return six.moves.input(self.PROMPT1 if firstline else self.PROMPT2)

    def testline(self, buffer):
        L = self.lua_runtime.lua_state
        buf = buffer.encode()
        status = ll.luaL_loadbuffer(L, buf, len(buf), b'=stdin')
        return status

    def incomplete(self, buffer):
        L = self.lua_runtime.lua_state
        status = self.testline(buffer)
        if status == ll.LUA_ERRSYNTAX:
            if lf.string(ll.lua_tostring(L, -1)).endswith(self.EOFMARK):
                ll.lua_pop(L, 1)
                return True
        return False

    def loadline(self):
        L = self.lua_runtime.lua_state
        lines = []
        firstline = True
        def pushline():
            lines.append(self.readline(firstline))
        pushline()
        firstline = False
        if self.testline('return {};'.format(lines[0])) != ll.LUA_OK:
            ll.lua_pop(L, 1)
            while self.incomplete('\n'.join(lines)):
                pushline()

    def docall(self):
        L = self.lua_runtime.lua_state
        ll.lua_getglobal(L, b'debug')
        ll.lua_pushstring(L, b'traceback')
        ll.lua_gettable(L, -2)
        ll.lua_insert(L, 1)
        ll.lua_pop(L, 1)
        status = ll.lua_pcall(L, 0, ll.LUA_MULTRET, 1)
        ll.lua_remove(L, 1)
        return status

    def print_result(self):
        L = self.lua_runtime.lua_state
        n = ll.lua_gettop(L)
        if n > 0:
            ll.lua_getglobal(L, b'print')
            ll.lua_insert(L, 1)
            if ll.lua_pcall(L, n, 0, 0) != ll.LUA_OK:
                six.print_("error calling 'print' ({})".format(lf.string(ll.lua_tostring(L, -1)).decode()), file=sys.stderr)

    def print_error(self):
        L = self.lua_runtime.lua_state
        n = ll.lua_gettop(L)
        if n > 0:
            n = n * 2 - 1
            for i in range(2, n, 2):
                ll.lua_pushstring(L, b'\t')
                ll.lua_insert(L, i)
            ll.lua_pushstring(L, b'\n')
            ll.lua_getglobal(L, b'io')
            ll.lua_pushstring(L, b'stderr')
            ll.lua_gettable(L, -2)
            ll.lua_pushstring(L, b'write')
            ll.lua_gettable(L, -2)
            ll.lua_insert(L, 1)
            ll.lua_insert(L, 2)
            ll.lua_pop(L, 1)
            if ll.lua_pcall(L, n + 2, 0, 0) != ll.LUA_OK:
                six.print_("error calling 'io.stderr:write' ({})".format(lf.string(ll.lua_tostring(L, -1)).decode()), file=sys.stderr)

    def dorepl(self):
        L = self.lua_runtime.lua_state
        try:
            while True:
                try:
                    assert ll.lua_gettop(L) == 0
                    self.loadline()
                    (self.print_result if self.docall() == ll.LUA_OK else self.print_error)()
                except KeyboardInterrupt:
                    six.print_('')
        except EOFError:
            six.print_('')


if __name__ == '__main__':
    repl = LuaREPL()
    repl.dorepl()
