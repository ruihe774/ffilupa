#!/usr/bin/env bash

rm -r ./**/__pycache__ __pycache__
rm *.c *.o *.so
rm ffilupa/*.c ffilupa/*.o ffilupa/*.so ffilupa/lua.json
rm -r build dist ffilupa.egg-info
