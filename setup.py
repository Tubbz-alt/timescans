#coding: utf8

"""
Setup script for timescans.
"""

from glob import glob


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name='timescans',
      version='0.0.1',
      author="TJ Lane",
      author_email="tjlane@slac.stanford.edu",
      description='time scan control',
      packages=["timescans"],
      package_dir={"timescans": "timescans"},
      scripts=[s for s in glob('scripts/*') if not s.endswith('__.py')],
      test_suite="test")
