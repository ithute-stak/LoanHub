#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>

// Native kernel boundary. It is intentionally non-authoritative.
// Rust/Python may call this only for benchmark-proven numerical workloads.
int main(int argc, char** argv) {
    if (argc != 4 || std::string(argv[1]) != "annuity") {
        std::cerr << "usage: loanhub_native annuity <principal> <monthly_rate>\n";
        return 2;
    }
    const long double principal = std::stold(argv[2]);
    const long double monthly_rate = std::stold(argv[3]);
    const long double one_month_interest = principal * monthly_rate;
    std::cout << std::fixed << std::setprecision(2) << one_month_interest << "\n";
    return 0;
}
