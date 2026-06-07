# Python bindings for ArchGeometry library
cmake_minimum_required(VERSION 3.14)

# Find pybind11
include(FetchContent)
FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.11.1
)
FetchContent_MakeAvailable(pybind11)

# Create Python module
pybind11_add_module(pyarchgeometry MODULE
    py_archgeometry.cpp
)

# Link to archgeometry library
target_link_libraries(pyarchgeometry PRIVATE archgeometry)

# Set output name
set_target_properties(pyarchgeometry PROPERTIES
    OUTPUT_NAME archgeometry
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/python"
)

# Install Python module
install(TARGETS pyarchgeometry
    LIBRARY DESTINATION python
)

# Copy __init__.py
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/__init__.py
    ${CMAKE_BINARY_DIR}/python/__init__.py
    COPYONLY
)
