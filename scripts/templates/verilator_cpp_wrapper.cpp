{% set objtype = 'V' + filename %}
#include <cstddef>
#include "verilated.h"
#include "{{ objtype }}.h"

const char* rules[] = {
{%- for rule in rules -%}
    "{{ rule }}",
{%- endfor -%}
};
const int num_rules = {{ rules|length }};

extern "C"
int get_num_rules() {
    return num_rules;
}
extern "C"
const char* get_rule(int x) {
    if ((x >= 0) && (x < num_rules)) return rules[x];
    else return "";
}

extern "C"
{{ objtype }}* construct() {
    Verilated::commandArgs(0, (const char**) nullptr);
    {{ objtype }}* top = new {{ objtype }}();
    top->FORCE_FIRE = 0;
    top->BLOCK_FIRE = 0;
    top->RST_N = 0; top->CLK = 0;
    top->eval();
    top->RST_N = 0; top->CLK = 1;
    top->eval();
    top->RST_N = 0; top->CLK = 0;
    top->eval();
    top->RST_N = 0; top->CLK = 1;
    top->eval();
    top->RST_N = 0; top->CLK = 0;
    top->eval();
    top->RST_N = 0; top->CLK = 1;
    top->eval();
    top->RST_N = 1; top->CLK = 1;
    top->eval();
    return top;
}
extern "C"
int set_CLK({{ objtype }}* top, int x) {
    top->CLK = x;
    return 0;
}
extern "C"
int eval({{ objtype }}* top) {
    top->eval();
    return 0;
}
extern "C"
int destruct({{ objtype }}* top) {
    if (top != nullptr) {
        delete top;
        top = nullptr;
    }
    return 0;
}

{% for signal in readable_signals %}
extern "C"
int get_{{ signal }}({{ objtype }}* top, int rule_num) {
    return 1 & (top->{{ signal }} >> rule_num);
}
{% endfor %}

{% for signal in writable_signals %}
extern "C"
int set_{{ signal }}({{ objtype }}* top, int rule_num, int val  ) {
    if (val == 0) { top->{{ signal }} &= ~(1 << rule_num);}
    else { top->{{ signal }} |= (1 << rule_num);}
    return 0;
}
{% endfor %}
