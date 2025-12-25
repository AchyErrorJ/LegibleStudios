cmake_minimum_required(VERSION 3.20)
project(ArchEngine VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

# Compiler flags
if(MSVC)
    add_compile_options(/W4 /permissive-)
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find Vulkan
find_package(Vulkan REQUIRED)

# FetchContent for dependencies
include(FetchContent)

# GLFW - window management
FetchContent_Declare(
    glfw
    GIT_REPOSITORY https://github.com/glfw/glfw.git
    GIT_TAG        3.3.8
)
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(glfw)

# GLM - math library
FetchContent_Declare(
    glm
    GIT_REPOSITORY https://github.com/g-truc/glm.git
    GIT_TAG        1.0.1
)
FetchContent_MakeAvailable(glm)

# nlohmann/json - JSON library for physics bridge
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
)
FetchContent_MakeAvailable(json)

# Dear ImGui - immediate mode GUI
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG        v1.90.1
)
FetchContent_MakeAvailable(imgui)

# ImGui doesn't have CMake, so we add sources manually
set(IMGUI_SOURCES
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_vulkan.cpp
)

# Source files
set(ENGINE_SOURCES
    src/main.cpp
    src/window.cpp
    src/memory.cpp
    src/vulkan_context.cpp
    src/pipeline.cpp
    src/mesh.cpp
    src/csg.cpp
    src/renderer.cpp
    src/physics_bridge.cpp
    src/geometry_loader.cpp
    src/imgui_layer.cpp
    src/obc_engine.cpp
    src/slicer_2d.cpp
    src/qbd_interface.cpp
    src/descriptor_manager.cpp
    src/instance_batch.cpp
    src/shadow_map.cpp
    src/environment_map.cpp
)

# Header files
set(ENGINE_HEADERS
    include/types.hpp
    include/window.hpp
    include/memory.hpp
    include/vulkan_context.hpp
    include/pipeline.hpp
    include/mesh.hpp
    include/renderer.hpp
    include/physics_bridge.hpp
    include/geometry_loader.hpp
    include/imgui_layer.hpp
    include/obc_engine.hpp
    include/slicer_2d.hpp
    include/qbd_interface.hpp
    include/descriptor_manager.hpp
    include/instance_batch.hpp
    include/shadow_map.hpp
    include/environment_map.hpp
)

# Main executable
add_executable(ArchEngine ${ENGINE_SOURCES} ${ENGINE_HEADERS} ${IMGUI_SOURCES})

target_include_directories(ArchEngine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/external
    ${Vulkan_INCLUDE_DIRS}
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
)

target_link_libraries(ArchEngine PRIVATE
    Vulkan::Vulkan
    glfw
    glm
    nlohmann_json::nlohmann_json
)

# Shader compilation
find_program(GLSLC glslc HINTS $ENV{VULKAN_SDK}/Bin)

if(GLSLC)
    file(GLOB SHADER_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.vert" "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.frag")

    foreach(SHADER ${SHADER_SOURCES})
        get_filename_component(SHADER_NAME ${SHADER} NAME)
        set(SHADER_OUTPUT "${CMAKE_CURRENT_SOURCE_DIR}/shaders/${SHADER_NAME}.spv")

        add_custom_command(
            OUTPUT ${SHADER_OUTPUT}
            COMMAND ${GLSLC} ${SHADER} -o ${SHADER_OUTPUT}
            DEPENDS ${SHADER}
            COMMENT "Compiling shader: ${SHADER_NAME}"
        )

        list(APPEND SHADER_OUTPUTS ${SHADER_OUTPUT})
    endforeach()

    add_custom_target(shaders DEPENDS ${SHADER_OUTPUTS})
    add_dependencies(ArchEngine shaders)
else()
    message(WARNING "glslc not found - shaders won't be compiled automatically")
endif()

# Copy shaders to build directory
add_custom_command(TARGET ArchEngine POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
    "${CMAKE_CURRENT_SOURCE_DIR}/shaders"
    "$<TARGET_FILE_DIR:ArchEngine>/shaders"
)

message(STATUS "Vulkan found: ${Vulkan_LIBRARIES}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
