cmake_minimum_required(VERSION 3.10)

# dummy target to bring libc++_shared.so into packages
add_library(visp_jni_shared STATIC dummy.cpp)
