LDFLAGS="-shared -fPIC"

obj_dir/Vour: our.v sim_main.cpp
	verilator -CFLAGS "-fPIC" -Wall --cc our.v --exe sim_main.cpp
	make -C obj_dir -j -f Vour.mk Vour  LDFLAGS=$(LDFLAGS)

clean:
	rm -rf obj_dir
