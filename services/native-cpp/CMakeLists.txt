cmake_minimum_required(VERSION 3.16)
project(loanhub_native LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(loanhub_native_core STATIC
    src/math.cpp
    src/loan.cpp
    src/accrual.cpp
    src/portfolio.cpp
    src/reconciliation.cpp
    src/predictive.cpp
)
target_include_directories(loanhub_native_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

add_executable(loanhub_native src/main.cpp)
target_link_libraries(loanhub_native PRIVATE loanhub_native_core)

add_library(loanhub_native_shared SHARED src/ffi.cpp)
target_link_libraries(loanhub_native_shared PRIVATE loanhub_native_core)
set_target_properties(loanhub_native_shared PROPERTIES OUTPUT_NAME "loanhub_native")
