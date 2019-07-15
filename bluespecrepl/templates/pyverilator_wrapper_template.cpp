{% set objtype = 'V' + top_module %}
#include <cstddef>
#include "verilated.h"
#include "verilated_vcd_c.h"
#include "{{ objtype }}.h"

// pyverilator defined values
// first declare variables as extern
extern const char* _pyverilator_module_name;
extern const uint32_t _pyverilator_num_inputs;
extern const char* _pyverilator_inputs[];
extern const uint32_t _pyverilator_input_widths[];
extern const uint32_t _pyverilator_num_outputs;
extern const char* _pyverilator_outputs[];
extern const uint32_t _pyverilator_output_widths[];
extern const uint32_t _pyverilator_num_internal_signals;
extern const char* _pyverilator_internal_signals[];
extern const uint32_t _pyverilator_internal_signal_widths[];
extern const uint32_t _pyverilator_num_internal_arrays;
extern const char* _pyverilator_internal_arrays[];
extern const uint32_t _pyverilator_internal_array_widths[];
extern const uint32_t _pyverilator_internal_array_depths[];
extern const uint32_t _pyverilator_num_rules;
extern const char* _pyverilator_rules[];
extern const char* _pyverilator_json_data;
// now initialize the variables
const char* _pyverilator_module_name = "{{ top_module }}";
const uint32_t _pyverilator_num_inputs = {{ inputs|length }};
const char* _pyverilator_inputs[] = {
{%- for name, size in inputs -%}
    "{{ name }}",
{%- endfor -%}
};
const uint32_t _pyverilator_input_widths[] = {
{%- for name, size in inputs -%}
    {{ size }},
{%- endfor -%}
};
const uint32_t _pyverilator_num_outputs = {{ outputs|length }};
const char* _pyverilator_outputs[] = {
{%- for name, size in outputs -%}
    "{{ name }}",
{%- endfor -%}
};
const uint32_t _pyverilator_output_widths[] = {
{%- for name, size in outputs -%}
    {{ size }},
{%- endfor -%}
};
const uint32_t _pyverilator_num_internal_signals = {{ internal_signals|length }};
const char* _pyverilator_internal_signals[] = {
{%- for name, size in internal_signals -%}
    "{{ name }}",
{%- endfor -%}
};
const uint32_t _pyverilator_internal_signal_widths[] = {
{%- for name, size in internal_signals -%}
    {{ size }},
{%- endfor -%}
};
const uint32_t _pyverilator_num_internal_arrays = {{ internal_arrays|length }};
const char* _pyverilator_internal_arrays[] = {
{%- for name, size, depth in internal_arrays -%}
    "{{ name }}",
{%- endfor -%}
};
const uint32_t _pyverilator_internal_array_widths[] = {
{%- for name, size, depth in internal_arrays -%}
    {{ size }},
{%- endfor -%}
};
const uint32_t _pyverilator_internal_array_depths[] = {
{%- for name, size, depth in internal_arrays -%}
    {{ depth }},
{%- endfor -%}
};
const uint32_t _pyverilator_num_rules = {{ rules|length }};
const char* _pyverilator_rules[] = {
{%- for name in rules -%}
    "{{ name }}",
{%- endfor -%}
};
const char* _pyverilator_json_data = {{ json_data|default('"null"') }};

// this is required by verilator for verilog designs using $time
// main_time is incremented in eval
double main_time = 0;
double sc_time_stamp() {
    return main_time;
}

// function definitions
// helper functions for basic verilator tasks
extern "C" {
{{ objtype }}* construct() {
    Verilated::commandArgs(0, (const char**) nullptr);
    Verilated::traceEverOn(true);
    {{ objtype }}* top = new {{ objtype }}();
    return top;
}
int eval({{ objtype }}* top) {
    top->eval();
    main_time++;
    return 0;
}
int destruct({{ objtype }}* top) {
    if (top != nullptr) {
        delete top;
        top = nullptr;
    }
    return 0;
}
VerilatedVcdC* start_vcd_trace({{ objtype }}* top, const char* filename) {
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open(filename);
    return tfp;
}
int add_to_vcd_trace(VerilatedVcdC* tfp, int time) {
    tfp->dump(time);
    return 0;
}
int flush_vcd_trace(VerilatedVcdC* tfp) {
    tfp->flush();
    return 0;
}
int stop_vcd_trace(VerilatedVcdC* tfp) {
    tfp->close();
    return 0;
}

// get input/output/internal_signal values
{% for ports in [outputs, inputs, internal_signals] -%}
{%- for name, size in ports -%}
{%- if size > 64 -%}
uint32_t get_{{ name }}({{ objtype }}* top, int word) {
    return top->{{ name }}[word];
}
{% elif size > 32 -%}
uint64_t get_{{ name }}({{ objtype }}* top) {
    return top->{{ name }};
}
{% else -%}
uint32_t get_{{ name }}({{ objtype }}* top) {
    return top->{{ name }};
}
{% endif -%}
{%- endfor -%}
{%- endfor %}

// get internal_array values
{% for name, size, depth in internal_arrays -%}
{%- if size > 64 -%}
uint32_t get_{{ name }}({{ objtype }}* top, int word, int index) {
    return top->{{ name }}[index][word];
}
{% elif size > 32 -%}
uint64_t get_{{ name }}({{ objtype }}* top, int index) {
    return top->{{ name }}[index];
}
{% else -%}
uint32_t get_{{ name }}({{ objtype }}* top, int index) {
    return top->{{ name }}[index];
}
{% endif -%}
{%- endfor %}

// set input values
{% for name, size in inputs -%}
{%- if size > 64 -%}
int set_{{ name }}({{ objtype }}* top, int word, uint64_t new_value) {
    top->{{ name }}[word] = new_value;
    return 0;
}
{% elif size > 32 -%}
int set_{{ name }}({{ objtype }}* top, uint64_t new_value) {
    top->{{ name }} = new_value;
    return 0;
}
{% else -%}
int set_{{ name }}({{ objtype }}* top, uint32_t new_value) {
    top->{{ name }} = new_value;
    return 0;
}
{% endif -%}
{%- endfor %}
}
