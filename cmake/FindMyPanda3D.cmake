# First option: panda3d built through makepanda
set(Panda3D_DIR)
if(${Panda3D_DIR})
else()
  set(Panda3D_DIR "$ENV{Panda3D_DIR}")
endif()

set(PANDA3D_LIBS
  panda p3framework p3direct
  p3dtoolconfig p3dtool pandaexpress pandaegg
  #p3ffmpeg p3interrogatedb p3tinydisplay p3vision
  #pandaai pandafx pandaphysics pandaskel
)

# Panda3D_DIR should point to the "built" directory generated by makepanda
if(Panda3D_DIR)
  # Find all libraries
  set(LIBRARY_PATHS "${Panda3D_DIR}/lib")
  set(INCLUDE_PATHS "${Panda3D_DIR}/include")
  set(Panda3D_BINARY_DIR "${Panda3D_DIR}/bin")

else() # Check for installed Panda3D
  set(LIBRARY_PATHS "/usr/lib" "/usr/lib/panda3d" "/usr/lib/x86_64-linux-gnu/panda3d")
  set(INCLUDE_PATHS "/usr/include/panda3d")
  set(Panda3D_BINARY_DIR "/usr/bin")
endif()


set(Panda3D_LIBRARIES "")
set(ALL_LIBS_FOUND TRUE)
foreach(lib_name ${PANDA3D_LIBS})
  find_library(Panda3D_${lib_name}_LIBRARY ${lib_name} PATHS ${LIBRARY_PATHS})
  if(Panda3D_${lib_name}_LIBRARY EQUAL "Panda3D_${lib_name}_LIBRARY-NOTFOUND")
    set(ALL_LIBS_FOUND FALSE)
  else()
    list(APPEND Panda3D_LIBRARIES "${Panda3D_${lib_name}_LIBRARY}")
  endif()
  mark_as_advanced(Panda3D_${lib_name}_LIBRARY)
endforeach()

find_path(Panda3D_INCLUDE_DIRS panda.h PATHS ${INCLUDE_PATHS})

include(FindPackageHandleStandardArgs)
# Handle the QUIETLY and REQUIRED arguments and set the DUMMYSDK_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args(Panda3D DEFAULT_MSG ALL_LIBS_FOUND Panda3D_INCLUDE_DIRS)
if(Panda3D_FOUND)
  mark_as_advanced(Panda3D_LIBRARIES Panda3D_INCLUDE_DIRS Panda3D_BINARY_DIR)

endif()
