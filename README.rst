BluespecREPL
============

A Python-based read-eval-print loop (REPL) environment for debugging Bluespec
System Verilog (BSV).

This is currently a work in progress.

Installing the bluespecrepl Package
-----------------------------------

Requirements
^^^^^^^^^^^^

``bluespecrepl`` uses pip for all the python requirements, but has some
additional non-python requirements:

- ``verilator`` - used for quick verilog simulation.
- ``gtkwave`` - used as a waveform viewer.
- ``iverilog`` - used by ``pyverilog`` to preprocess verilog files.

All of these can be installed in Ubuntu using ``apt get install``.

Installing for Development
^^^^^^^^^^^^^^^^^^^^^^^^^^

To install this package for development, you should use a virtual environment,
and install the package in editable mode using pip.

To create a virtual environment for this project, run the command below.
If it fails, just look online to see what you need to install to make it work.

    $ python3 -m venv path/to/new-venv-folder

To start using your new virtual environment, run the command below.
This needs to be run each time you open a new terminal.

    $ source path/to/new-venv-folder/bin/activate

At this point you are now using your new virtual environment.
Python packages you install in this environment will not be available outside
your virtual environment.
If you want to stop using the virtual environment, just run ``deactivate``.

To install the ``bluespecrepl`` package in editable mode, inside the
``bluespecrepl`` folder, run the command below.

    $ pip3 install -e .

This will install the dependencies from PyPI automatically (if necessary).

Some changes to ``bluespecrepl`` may require changes to ``bluespecrepl``'s
respective dependencies, so it may be useful to install ``pyverilator`` and
``tclwrapper`` locally in editable mode.

Installing Non-Development Version
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to just install the bluespecrepl package, you should be able to
using the following command:

    $ pip3 install git+https://github.com/csail-csg/bluespecrepl.git

Modules
-------

bsvproject
^^^^^^^^^^

Management, compilation, and simulation of BSV projects in python.

pyverilatorbsv
^^^^^^^^^^^^^^

BSV-specific version of pyverilator that allows for opening up GTKWave and
viewing signals using their BSV type.

