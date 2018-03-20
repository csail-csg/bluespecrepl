// This is a custom version of the enum program that comes with the Bluespec
// compiler. Unlike the original version, this version stops when it receives
// an EOF character from stdin.

#include <string>
#include <iostream>
#include <vector>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "ERROR: " << argv[0] << " expects exactly one argument!" << std::endl;
        return -1;
    }

    std::vector<std::string> enum_values;

    // Parse arguments
    {
        std::string argstring(argv[1]);
        size_t enum_val_start = 0;
        size_t enum_val_end = 0;
        while (enum_val_start < argstring.length()) {
            enum_val_end = argstring.find(' ', enum_val_start);
            if (enum_val_end == std::string::npos) {
                // no space found
                enum_val_end = argstring.length();
            } else if (enum_val_end == enum_val_start) {
                enum_val_start++;
                continue;
            }
            
            enum_values.push_back(argstring.substr(enum_val_start, enum_val_end - enum_val_start));
            enum_val_start = enum_val_end;
        }
    }

    std::string input;
    unsigned long i;

    while(std::getline(std::cin, input)) {
        i = std::stoul(input, 0, 16);
        if (i >= enum_values.size()) {
            std::cout << "UNDEF(" << std::hex << i << ")" << std::endl;
        } else {
            std::cout << enum_values[i] << std::endl;
        }
    }

    return 0;
}
