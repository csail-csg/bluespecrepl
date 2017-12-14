#!/bin/bash

set -e
set -x

BUILD_DIR=./build
INFO_DIR=./info
SIM_DIR=./sim
SCRIPT_DIR=../../scripts
BSV_FILE_NAME=ComplexRuleScheduling.bsv
BSV_MODULE_NAME=mkComplexRuleScheduling
INFO_FLAGS="-sched-dot -show-method-bvi"

rm -rf $INFO_DIR $BUILD_DIR $SIM_DIR
mkdir -p $BUILD_DIR
mkdir -p $INFO_DIR
mkdir -p $SIM_DIR

# compile to verilog
bsc -no-opt-ATS -keep-fires $INFO_FLAGS -aggressive-conditions -verilog -bdir $BUILD_DIR -vdir $BUILD_DIR -info-dir $INFO_DIR -g $BSV_MODULE_NAME $BSV_FILE_NAME
# compile to bluesim too
bsc -no-opt-ATS -keep-fires $INFO_FLAGS -aggressive-conditions -sim -bdir $BUILD_DIR -vdir $BUILD_DIR -info-dir $INFO_DIR -simdir $SIM_DIR -g $BSV_MODULE_NAME $BSV_FILE_NAME
bsc -no-opt-ATS -keep-fires $INFO_FLAGS -aggressive-conditions -sim -bdir $BUILD_DIR -vdir $BUILD_DIR -info-dir $INFO_DIR -simdir $SIM_DIR -e $BSV_MODULE_NAME -o $SIM_DIR/a.out

# instrument the verilog to provide access to WILL_FIRE overrides
$SCRIPT_DIR/insert_manual_scheduling_overrides.py $BUILD_DIR/$BSV_MODULE_NAME.v

verilator -Wno-fatal --CFLAGS " -fPIC --std=c++11 " -y $BUILD_DIR --cc $BUILD_DIR/$BSV_MODULE_NAME.v --exe $BUILD_DIR/${BSV_MODULE_NAME}_wrapper.cpp

make -C obj_dir -f V$BSV_MODULE_NAME.mk CFLAGS=" -fPIC -shared " LDFLAGS=" -fPIC -shared "
