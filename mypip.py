def pip(*args):
    import pip
    try:
        pip.main(list(args))
    except SystemExit as e:
        return e.code
    else:
        return 0
