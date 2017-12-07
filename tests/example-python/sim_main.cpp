#include <iostream>

#include "Vour.h"
#include "verilated.h"
#include "Vour_our.h" 

Vour* top;

extern "C"
int init(char **argv){
    Verilated::commandArgs(0, argv);
    top = new Vour;
}

extern "C"
int get_x(){
    return top->our->x;
}

extern "C"
void* set_x(int signal){
  top->our->x = signal;
}

extern "C"
int step(){
      if (top->clock)
      std::cout << "y is " << top->our->y << std::endl;
      top->clock ^= 1;
      top->eval();
}

extern "C"
void* finish_verilator(){
    std::cout << "Destruct verilator object" << std::endl;
    delete top;
}
