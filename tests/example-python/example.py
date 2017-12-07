#!/usr/bin/python3
import ctypes

lib = ctypes.CDLL("obj_dir/Vour")
lib.init(None)
lib.step()
lib.step()
lib.set_x(12)
print("Set up x to 12")
lib.step()
lib.step()
lib.finish_verilator()
