cmake_minimum_required(VERSION 3.10)

project(tutorial-bridge-opencv)

find_package(VISP REQUIRED visp_core visp_io)

set(tutorial_cpp
  tutorial-bridge-opencv-camera-param.cpp
  tutorial-bridge-opencv-image.cpp
  tutorial-bridge-opencv-matrix.cpp)

list(APPEND tutorial_data "${CMAKE_CURRENT_SOURCE_DIR}/chessboard.jpeg" )
list(APPEND tutorial_data "${CMAKE_CURRENT_SOURCE_DIR}/monkey.jpeg" )

foreach(cpp ${tutorial_cpp})
  visp_add_target(${cpp})
  if(COMMAND visp_add_dependency)
    visp_add_dependency(${cpp} "tutorials")
  endif()
endforeach()

# Copy the data files to the same location than the target
foreach(data ${tutorial_data})
  visp_copy_data(tutorial-bridge-opencv-camera-param.cpp ${data})
endforeach()
