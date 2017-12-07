#!/bin/bash

set -e
set -x

BUILD_DIR=./build
SCRIPT_DIR=../../scripts
BSV_FILE_NAME=SimpleIntegration.bsv
BSV_MODULE_NAME=mkSimpleIntegration

mkdir -p $BUILD_DIR

# compile to verilog
bsc -no-opt-ATS -keep-fires -aggressive-conditions -verilog -bdir $BUILD_DIR -vdir $BUILD_DIR -g $BSV_MODULE_NAME $BSV_FILE_NAME

# compile to bluesim
#bsc -no-opt-ATS -keep-fires -aggressive-conditions -sim -bdir $BUILD_DIR -simdir $BUILD_DIR -g $BSV_MODULE_NAME $BSV_FILE_NAME
#bsc -no-opt-ATS -keep-fires -aggressive-conditions -sim -bdir $BUILD_DIR -simdir $BUILD_DIR -e $BSV_MODULE_NAME -o $BUILD_DIR/a.out

# instrument the verilog to provide access to WILL_FIRE overrides
$SCRIPT_DIR/insert_manual_scheduling_overrides.py $BUILD_DIR/$BSV_MODULE_NAME.v

verilator -Wno-fatal --CFLAGS " -fPIC --std=c++11 " --cc $BUILD_DIR/$BSV_MODULE_NAME.v --exe $BUILD_DIR/${BSV_MODULE_NAME}_wrapper.cpp

make -C obj_dir -f V$BSV_MODULE_NAME.mk CFLAGS=" -fPIC -shared " LDFLAGS=" -fPIC -shared "
