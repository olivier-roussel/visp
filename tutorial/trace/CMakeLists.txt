cmake_minimum_required(VERSION 3.10)

project(tutorial-trace)

find_package(VISP REQUIRED visp_core)

# set the list of source files
set(tutorial_cpp
  tutorial-trace.cpp)

foreach(cpp ${tutorial_cpp})
  visp_add_target(${cpp})
  if(COMMAND visp_add_dependency)
    visp_add_dependency(${cpp} "tutorials")
  endif()
endforeach()
