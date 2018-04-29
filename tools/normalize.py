#!/usr/bin/env python3

import os
import re
from subprocess import run, PIPE

out = run(('git', 'rev-parse', '--show-toplevel'), check=True, universal_newlines=True, stdout=PIPE).stdout
os.chdir(out.rstrip())
out = run(('git', 'ls-files'), check=True, universal_newlines=True, stdout=PIPE).stdout
files = out.splitlines()
fe = re.compile(r'(?:\r\n|\r)$')
for fn in files:
    with open(fn, 'r+') as f:
        print('processing', fn, '...', end=' ', sep=' ')
        rst = []
        modified = False
        for ln in f:
            r = fe.sub('\n', ln)
            if r.rstrip() == '':
                r = '\n'
            if r != ln:
                modified = True
            rst.append(r)
        while rst and rst[-1].rstrip() == '':
            rst.pop()
            modified = True
        if rst[-1][-1] != '\n':
            rst[-1] += '\n'
        if modified:
            f.seek(0)
            f.truncate()
            f.writelines(rst)
            print('\x1b[7;1mmodified\x1b[0m')
        else:
            print('nothing')
