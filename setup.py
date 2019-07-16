# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
# from codecs import open
# from os import path

# here = path.abspath(path.dirname(__file__))
# # Get the long description from the README file
# with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
#     long_description = f.read()

setup(
    name='BluespecREPL',
    version='0.0.1',
    description='Python-based REPL interface for debugging Bluespec System Verilog',
    # long_description=long_description,
    url='https://github.mit.edu/acwright/bluespec-repl',
    author='Andy Wright',
    author_email='acwright@mit.edu',
    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Hardware',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='Bluespec hardware repl development',
    packages=find_packages(exclude=['examples', 'tests', 'util']),
    include_package_data=True,
    install_requires=[
        'Jinja2', # Jinja2 (2.10)
        'pyverilog', #pyverilog (1.1.1)
    ],
    extras_require={
        'dev': [], # ['check-manifest'],
        'test': [], # ['coverage'],
    },
    entry_points={
        # If we ever want to add an executable script, this is where it goes
    },
    project_urls={
        'Bug Reports': 'https://github.mit.edu/acwright/bluespec-repl/issues',
        'Source': 'https://github.mit.edu/acwright/bluespec-repl',
    },
)
