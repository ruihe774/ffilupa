ifneq ($(shell python --version),)
PYTHON := python
else
ifneq ($(shell python3 --version),)
PYTHON := python3
else
$(error python3 is not found)
endif
endif

all:
	@echo --- build
	@echo LUA_LIBDIR: $(LUA_LIBDIR)
	@echo LUA_INCDIR: $(LUA_INCDIR)
	@echo LUA: $(LUA)
	@echo PYTHON: $(PYTHON)
	-rm _ffilupa.*
	$(PYTHON) build_embedding.py --library_dirs $(LUA_LIBDIR) --include_dirs $(LUA_INCDIR) --lua $(LUA) --target '_ffilupa.*' --verbose

install:
	@echo --- install
	@echo LIBDIR: $(LIBDIR)
	@echo LUADIR: $(LUADIR)
	cp -r _ffilupa.* ffilupa '$(LIBDIR)'
	cp ffilupa.lua '$(LUADIR)'
