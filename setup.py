# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='BluespecREPL',
    version='0.3.1',
    description='Python-based REPL interface for simulating and debugging Bluespec System Verilog',
    # long_description=long_description,
    url='https://github.com/csail-csg/bluespecrepl',
    author='CSAIL CSG',
    author_email='acwright@mit.edu, bthom@mit.edu',
    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)',
        'Topic :: System :: Hardware',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='Bluespec BSV hardware repl simulation',
    packages=find_packages(exclude=['examples', 'tests', 'util']),
    include_package_data=True,
    install_requires=[
        'pyverilator>=0.4.0',
        'tclwrapper',
        'pyverilog', #pyverilog (1.1.1)
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    entry_points={
        # If we ever want to add an executable script, this is where it goes
    },
    project_urls={
        'Bug Reports': 'https://github.com/csail-csg/bluespecrepl/issues',
        'Source': 'https://github.com/csail-csg/bluespecrepl',
    },
)
