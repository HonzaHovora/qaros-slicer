#pragma once
// Let VTK choose its GL loader; do not mix GLEW and GLAD in one translation unit.
#if __has_include(<vtk_glad.h>)
#include <vtk_glad.h>
#else
#include <vtk_glew.h>
#endif
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>
