from __future__ import absolute_import

import unittest
import doctest
import os

import ffilupa


def suite():
    suite = unittest.defaultTestLoader.loadTestsFromNames(('ffilupa.tests.test',))
    suite.addTest(doctest.DocTestSuite(ffilupa))
    return suite
