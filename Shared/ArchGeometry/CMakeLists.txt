cmake_minimum_required(VERSION 3.16)
project(ArchGeometry VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Options
option(ARCHGEOMETRY_BUILD_PYTHON "Build Python bindings" ON)
option(ARCHGEOMETRY_BUILD_TESTS "Build tests" ON)
option(ARCHGEOMETRY_BUILD_SHARED "Build as shared library" ON)

# Dependencies via FetchContent
include(FetchContent)

# nlohmann/json
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(json)

# glm (header-only math library)
FetchContent_Declare(
    glm
    GIT_REPOSITORY https://github.com/g-truc/glm.git
    GIT_TAG 1.0.1
)
FetchContent_MakeAvailable(glm)

# Source files
set(ARCHGEOMETRY_SOURCES
    src/archgeometry.cpp
    src/schema_parser.cpp
    src/wall_geometry.cpp
    src/floor_geometry.cpp
    src/roof_geometry.cpp
    src/opening_geometry.cpp
    src/room_geometry.cpp
    src/query_api.cpp
)

# Create library
if(ARCHGEOMETRY_BUILD_SHARED)
    add_library(archgeometry SHARED ${ARCHGEOMETRY_SOURCES})
    target_compile_definitions(archgeometry PRIVATE ARCHGEOMETRY_EXPORTS)
    if(WIN32)
        target_compile_definitions(archgeometry PUBLIC ARCHGEOMETRY_DLL)
    endif()
else()
    add_library(archgeometry STATIC ${ARCHGEOMETRY_SOURCES})
endif()

# Include directories
target_include_directories(archgeometry
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# Link dependencies
target_link_libraries(archgeometry
    PUBLIC
        nlohmann_json::nlohmann_json
        glm::glm
)

# Export symbols for DLL
if(WIN32 AND ARCHGEOMETRY_BUILD_SHARED)
    set_target_properties(archgeometry PROPERTIES
        WINDOWS_EXPORT_ALL_SYMBOLS ON
    )
endif()

# Python bindings
if(ARCHGEOMETRY_BUILD_PYTHON)
    add_subdirectory(bindings/python)
endif()

# Tests
if(ARCHGEOMETRY_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# Tools — built unconditionally; small CLI utilities that link against the lib.
add_executable(archgeometry_dump tools/archgeometry_dump.cpp)
target_link_libraries(archgeometry_dump PRIVATE archgeometry)
set_target_properties(archgeometry_dump PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/tools"
)

# Install rules (simplified - no export for FetchContent dependencies)
install(TARGETS archgeometry
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(DIRECTORY include/archgeometry
    DESTINATION include
)
