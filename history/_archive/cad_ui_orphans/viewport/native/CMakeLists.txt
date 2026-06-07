cmake_minimum_required(VERSION 3.16)
project(archengine_viewport VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows only
if(NOT WIN32)
    message(FATAL_ERROR "This library only supports Windows")
endif()

# Find required libraries
find_package(OpenGL REQUIRED)

# Source files
set(SOURCES
    viewport_bridge.cpp
    viewport_bridge.h
    ipc_client.cpp
    ipc_client.h
)

# Create shared library
add_library(archengine_viewport SHARED ${SOURCES})

# Link libraries
target_link_libraries(archengine_viewport PRIVATE
    OpenGL::GL
    d3d11
    dxgi
)

# Export symbols
target_compile_definitions(archengine_viewport PRIVATE VIEWPORT_EXPORTS)

# Install
install(TARGETS archengine_viewport
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
)
