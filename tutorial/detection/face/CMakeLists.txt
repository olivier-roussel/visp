cmake_minimum_required(VERSION 3.10)

project(tutorial-detection-face)

find_package(VISP REQUIRED visp_detection visp_io visp_gui visp_sensor)

# set the list of source files
set(tutorial_cpp
  tutorial-face-detector.cpp
  tutorial-face-detector-live.cpp
  tutorial-face-detector-live-threaded.cpp)

list(APPEND tutorial_data "${CMAKE_CURRENT_SOURCE_DIR}/haarcascade_frontalface_alt.xml" )
list(APPEND tutorial_data "${CMAKE_CURRENT_SOURCE_DIR}/video.mp4" )

foreach(cpp ${tutorial_cpp})
  visp_add_target(${cpp})
  if(COMMAND visp_add_dependency)
    visp_add_dependency(${cpp} "tutorials")
  endif()
endforeach()

# Copy the data files to the same location than the target
foreach(data ${tutorial_data})
  visp_copy_data(tutorial-face-detector-live.cpp ${data})
endforeach()
