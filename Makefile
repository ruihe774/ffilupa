ifneq ($(shell python --version),)
PYTHON := python
else
ifneq ($(shell python3 --version),)
PYTHON := python3
else
$(error python3 is not found)
endif
endif

LUA_VERSION := $(subst lua,,$(LUA))

all:
	@echo --- build
	@echo LUA_LIBDIR: $(LUA_LIBDIR)
	@echo LUA_INCDIR: $(LUA_INCDIR)
	@echo LUA: $(LUA)
	@echo LUA_VERSION: $(LUA_VERSION)
	@echo PYTHON: $(PYTHON)
	-rm _ffilupa.*
	$(PYTHON) build_embedding.py --library_dirs $(LUA_LIBDIR) --include_dirs $(LUA_INCDIR) --version $(LUA_VERSION) --target '_ffilupa.*' --verbose

install:
	@echo --- install
	@echo LIBDIR: $(LIBDIR)
	@echo LUADIR: $(LUADIR)
	cp -r _ffilupa.* ffilupa '$(LIBDIR)'
	cp ffilupa.lua '$(LUADIR)'
