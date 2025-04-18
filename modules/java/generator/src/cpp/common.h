// This file is part of ViSP project.

#ifndef _VISP_JAVA_COMMON_H_
#define _VISP_JAVA_COMMON_H_

#include <stdexcept>
#include <string>

extern "C" {

#if !defined(__ppc__)
// to suppress warning from jni.h on OS X
#define TARGET_RT_MAC_CFM 0
#endif
#include <jni.h>

} // extern "C"

#include "listconverters.hpp"
#include "visp_java.hpp"
#include <visp3/core/vpConfig.h>

#ifdef _MSC_VER
#pragma warning(disable : 4800 4244)
#endif

#endif //_VISP_JAVA_COMMON_H_
