cmake_minimum_required(VERSION 3.16)
project(loanhub_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_executable(loanhub_native src/main.cpp)

add_library(loanhub_native_shared SHARED src/main.cpp)
target_compile_definitions(loanhub_native_shared PRIVATE LOANHUB_NATIVE_LIBRARY=1)
set_target_properties(
    loanhub_native_shared
    PROPERTIES
        OUTPUT_NAME "loanhub_native"
)
