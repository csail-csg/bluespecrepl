import os
import struct
from bluespecrepl import bsvproject, bsvutil

# helper functions for converting between floating point types and bit types
def float_to_bit32(f):
    bytes_ = struct.pack('f', f)
    b32 = struct.unpack('i', bytes_)[0]
    return b32

def bit32_to_float(b32):
    bytes_ = struct.pack('i', b32)
    f = struct.unpack('f', bytes_)[0]
    return f

def double_to_bit64(d):
    bytes_ = struct.pack('d', d)
    b64 = struct.unpack('l', bytes_)[0]
    return b64

def bit64_to_double(b64):
    bytes_ = struct.pack('l', b64)
    d = struct.unpack('d', bytes_)[0]
    return d

# setup build directory and cd to it
build_dir = os.path.join(os.path.dirname(__file__), 'build', os.path.basename(__file__))
os.makedirs(build_dir, exist_ok = True)
os.chdir(build_dir)

# create the FPDividerTest bsv file
# use add_line_macro to get useful file and line numbers from the bluespec compiler in case of errors
bsv = bsvutil.add_line_macro('''
import FloatingPoint::*;
import Divide::*;
import ClientServer::*;
import GetPut::*;

interface FPDividerTest;
    // single-precision
    method Action req32(Float a, Float b);
    method ActionValue#(Float) resp32();
    // double-precision
    method Action req64(Double a, Double b);
    method ActionValue#(Double) resp64();
endinterface

(* synthesize *)
module mkFPDividerTest(FPDividerTest);
    let int_div_32 <- mkDivider(1);
    Server#(Tuple3#(Float, Float, RoundMode), Tuple2#(Float, Exception)) fp_div_32 <- mkFloatingPointDivider(int_div_32);

    let int_div_64 <- mkDivider(2);
    Server#(Tuple3#(Double, Double, RoundMode), Tuple2#(Double, Exception)) fp_div_64 <- mkFloatingPointDivider(int_div_64);

    method Action req32(Float a, Float b);
        fp_div_32.request.put(tuple3(a, b, Rnd_Nearest_Even));
    endmethod
    method ActionValue#(Float) resp32;
        let ret <- fp_div_32.response.get();
        return tpl_1(ret);
    endmethod

    method Action req64(Double a, Double b);
        fp_div_64.request.put(tuple3(a, b, Rnd_Nearest_Even));
    endmethod
    method ActionValue#(Double) resp64;
        let ret <- fp_div_64.response.get();
        return tpl_1(ret);
    endmethod
endmodule
''')
with open('FPDividerTest.bsv', 'w') as f:
    f.write(bsv)

# create a project 
proj = bsvproject.BSVProject('FPDividerTest.bsv', 'mkFPDividerTest')
sim = proj.gen_python_repl()

# function for single precision division
def div32(f1, f2):
    b1 = float_to_bit32(f1)
    b2 = float_to_bit32(f2)
    sim.interface.req32(b1, b2)
    while not sim.interface.resp32.ready:
        sim.step()
    b3 = sim.interface.resp32()
    f3 = bit32_to_float(b3)
    print('%s / %s = %s (%f / %f = %f)' % (hex(b1), hex(b2), hex(b3), f1, f2, f3))
    return f3

# function for double precision division
def div64(f1, f2):
    b1 = double_to_bit64(f1)
    b2 = double_to_bit64(f2)
    sim.interface.req64(b1, b2)
    while not sim.interface.resp64.ready:
        sim.step()
    b3 = sim.interface.resp64()
    f3 = bit64_to_double(b3)
    print('%s / %s = %s (%f / %f = %f)' % (hex(b1), hex(b2), hex(b3), f1, f2, f3))
    return f3

# a few simple tests
div32(21, 1.4)
div64(21, 1.4)

div32(1, 3)
div64(1, 3)
