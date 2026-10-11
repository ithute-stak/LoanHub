#include <cassert>
#include <cstring>
#include <string>
extern "C" int loanhub_native_execute(const char*, const char*, char*, std::size_t);
int main() {
    char result[1024]{};
    const char* rows = "101|10000|0\n201|0|10000\n";
    auto size = loanhub_native_execute("accounting-journal-validate", rows, result, sizeof(result));
    assert(size > 0 && std::string(result) == "balanced\n");
    size = loanhub_native_execute("accounting-trial-balance", rows, result, sizeof(result));
    assert(size > 0 && std::string(result) == "10000|10000\n101|10000|0|10000\n201|0|10000|-10000\n");
    size = loanhub_native_execute("accounting-journal-validate", "101|10000|0\n201|0|9999\n", result, sizeof(result));
    assert(size == -3);
    size = loanhub_native_execute("accounting-journal-validate", "invalid", result, sizeof(result));
    assert(size == -3);
    size = loanhub_native_execute("accounting-trial-balance", rows, result, 3);
    assert(size == -2);
}
