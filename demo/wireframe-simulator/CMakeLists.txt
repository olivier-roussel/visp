#############################################################################
#
# ViSP, open source Visual Servoing Platform software.
# Copyright (C) 2005 - 2023 by Inria. All rights reserved.
#
# This software is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See the file LICENSE.txt at the root directory of this source
# distribution for additional information about the GNU GPL.
#
# For using ViSP with software that can not be combined with the GNU
# GPL, please contact Inria about acquiring a ViSP Professional
# Edition License.
#
# See https://visp.inria.fr for more information.
#
# This software was developed at:
# Inria Rennes - Bretagne Atlantique
# Campus Universitaire de Beaulieu
# 35042 Rennes Cedex
# France
#
# If you have questions regarding the use of this file, please contact
# Inria at visp@inria.fr
#
# This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
# WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
# Description:
# ViSP overall configuration file.
#
#############################################################################

cmake_minimum_required(VERSION 3.10)

project(demo-wireframe-simulator)

find_package(VISP REQUIRED visp_core visp_robot visp_vs visp_io visp_gui)

# SOURCE variable corresponds to the list of all the sources to build binaries.
# The generate binary comes by removing the .cpp extension to
# the source name.
#
# If you want to add/remove a source, modify here
set(demo_cpp
  servoSimu4Points.cpp
  servoSimuCylinder.cpp
  servoSimuSphere.cpp
)

set(demo_data "${CMAKE_CURRENT_SOURCE_DIR}/mire.png")

foreach(cpp ${demo_cpp})
  visp_add_target(${cpp})
  if(COMMAND visp_add_dependency)
    visp_add_dependency(${cpp} "demos")
  endif()
endforeach()

# Copy the data files to the same location than the target
foreach(data ${demo_data})
  visp_copy_data(servoSimu4Points.cpp ${data})
endforeach()

# Add test
# To run some of these tests don't forget to set VISP_INPUT_IMAGE_PATH
# environment variable to the ViSP test sequences location.
# To get these sequence download ViSP-images.tar.gz from
# https://visp.inria.fr/download/
add_test(servoSimu4Points servoSimu4Points -d -p)
add_test(servoSimuCylinder servoSimuCylinder -d -p)
add_test(servoSimuSphere servoSimuSphere -d -p)
