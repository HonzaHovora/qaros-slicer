cmake_minimum_required(VERSION 3.20)
project(QarosVTK)
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})
set(EXTENSION_HOMEPAGE "https://github.com/HonzaHovora/QAROS_VTK")
set(EXTENSION_CATEGORY "QAROS")
set(EXTENSION_CONTRIBUTORS "QuaternAR")
set(EXTENSION_DESCRIPTION "Stream lit models, segmentations and scalar CT/MR volumes using a separate QAROS VTK backend.")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA")
slicerMacroBuildScriptedModule(NAME QarosVTK SCRIPTS QarosVTK.py)
slicerMacroBuildScriptedModule(NAME QarosLive SCRIPTS QarosLive.py)
set(library_dir ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/QarosVTKLib)
file(MAKE_DIRECTORY ${library_dir})
file(WRITE ${library_dir}/__init__.py "\"\"\"QAROS support package.\"\"\"\n")
configure_file(qarvtk_slicer.py ${library_dir}/qarvtk_slicer.py COPYONLY)
configure_file(qarvtk_host_view.py ${library_dir}/qarvtk_host_view.py COPYONLY)
configure_file(qarvtk_host_gpu.py ${library_dir}/qarvtk_host_gpu.py COPYONLY)
configure_file(qarvtk_host_runtime.py ${library_dir}/qarvtk_host_runtime.py COPYONLY)
configure_file(../qarvtk_scene.py ${library_dir}/qarvtk_scene.py COPYONLY)
configure_file(../qarvtk_bridge.py ${library_dir}/qarvtk_bridge.py COPYONLY)
configure_file(../qarvtk_runtime.py ${library_dir}/qarvtk_runtime.py COPYONLY)
install(FILES
  ${library_dir}/__init__.py
  ${library_dir}/qarvtk_slicer.py
  ${library_dir}/qarvtk_host_view.py
  ${library_dir}/qarvtk_host_gpu.py
  ${library_dir}/qarvtk_host_runtime.py
  ${library_dir}/qarvtk_scene.py
  ${library_dir}/qarvtk_bridge.py
  ${library_dir}/qarvtk_runtime.py
  DESTINATION ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/QarosVTKLib
  COMPONENT RuntimeLibraries)
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
