from subprocess import check_output

files = check_output(('git', 'ls-files', '--recurse-submodules'), universal_newlines=True, encoding='ascii').splitlines()
with open('MANIFEST.in', 'w', encoding='ascii') as f:
    f.writelines('include ' + file + '\n' for file in files)
