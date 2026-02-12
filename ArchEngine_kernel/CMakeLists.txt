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
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
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

# ArchGeometry - shared geometry library (single source of truth for schema interpretation)
# Disable tests/python for kernel build to speed up compilation
set(ARCHGEOMETRY_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ARCHGEOMETRY_BUILD_PYTHON OFF CACHE BOOL "" FORCE)
set(ARCHGEOMETRY_BUILD_SHARED OFF CACHE BOOL "" FORCE)  # Static link for kernel
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../Shared/ArchGeometry
                 ${CMAKE_CURRENT_BINARY_DIR}/archgeometry)

# Dear ImGui - immediate mode GUI
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG        v1.90.1
)
FetchContent_MakeAvailable(imgui)

# cpp-httplib - header-only HTTP library for LLM integration
# We fetch it but only use it header-only (don't use the CMake target to avoid OpenSSL detection)
FetchContent_Declare(
    httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG        v0.15.3
)
FetchContent_GetProperties(httplib)
if(NOT httplib_POPULATED)
    FetchContent_Populate(httplib)
endif()
# Create interface library for header-only usage without SSL
add_library(httplib_no_ssl INTERFACE)
target_include_directories(httplib_no_ssl INTERFACE ${httplib_SOURCE_DIR})

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
    src/ipc_server.cpp
    src/post_process.cpp
    src/texture.cpp
    src/project.cpp
    src/llm_assistant.cpp
    src/memory_test.cpp
    src/bvh.cpp
    src/path_tracer.cpp
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
    include/ipc_server.hpp
    include/post_process.hpp
    include/texture.hpp
    include/project.hpp
    include/llm_assistant.hpp
    include/bvh.hpp
    include/path_tracer.hpp
)

# Library sources (excludes main.cpp, includes arch_api.cpp)
set(LIB_SOURCES
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
    src/ipc_server.cpp
    src/post_process.cpp
    src/arch_api.cpp
    src/texture.cpp
    src/project.cpp
    src/llm_assistant.cpp
    src/memory_test.cpp
    src/bvh.cpp
    src/path_tracer.cpp
)

# Shared library (DLL) for embedding in Qt/Python
add_library(ArchEngineLib SHARED ${LIB_SOURCES} ${ENGINE_HEADERS} ${IMGUI_SOURCES})

target_include_directories(ArchEngineLib PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/external
    ${Vulkan_INCLUDE_DIRS}
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
)

target_link_libraries(ArchEngineLib PRIVATE
    Vulkan::Vulkan
    glfw
    glm
    nlohmann_json::nlohmann_json
    archgeometry
    httplib_no_ssl
)

target_compile_definitions(ArchEngineLib PRIVATE ARCHENGINE_EXPORTS)

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
    archgeometry
    httplib_no_ssl
)

# Shader compilation
find_program(GLSLC glslc HINTS $ENV{VULKAN_SDK}/Bin)

if(GLSLC)
    file(GLOB SHADER_SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.vert"
        "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.frag"
        "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.comp"
        "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.tesc"
        "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.tese"
    )

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

# ============================================================================
# CPack Configuration for Installer
# ============================================================================

set(CPACK_PACKAGE_NAME "ArchEngine")
set(CPACK_PACKAGE_VENDOR "ArchEngine Suite")
set(CPACK_PACKAGE_VERSION_MAJOR 0)
set(CPACK_PACKAGE_VERSION_MINOR 1)
set(CPACK_PACKAGE_VERSION_PATCH 0)
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "ArchEngine Kernel - Architectural Visualization Engine")
set(CPACK_PACKAGE_DESCRIPTION "Real-time architectural visualization engine with PBR rendering, tessellation, and material editing capabilities")

# Set installer filename
set(CPACK_OUTPUT_FILE_PREFIX "${CMAKE_SOURCE_DIR}/dist")

# Windows-specific settings
if(WIN32)
    # Use only ZIP if NSIS is not available
    set(CPACK_GENERATOR "ZIP")
    set(CPACK_PACKAGE_INSTALL_DIRECTORY "ArchEngine")
    set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY "ArchEngine")

    # NSIS-specific settings
    set(CPACK_NSIS_DISPLAY_NAME "ArchEngine")
    set(CPACK_NSIS_PACKAGE_NAME "ArchEngine")
    set(CPACK_NSIS_URL_INFO_ABOUT "https://github.com/yourusername/ArchEngine")
    set(CPACK_NSIS_CONTACT "your-email@example.com")
    set(CPACK_NSIS_HELP_LINK "https://github.com/yourusername/ArchEngine/issues")
    set(CPACK_NSIS_MODIFY_PATH ON)

    # Create desktop shortcut
    set(CPACK_NSIS_CREATE_ICONS_EXTRA "
        CreateShortCut '$DESKTOP\\\\ArchEngine.lnk' '$INSTDIR\\\\ArchEngine.exe'
    ")

    # Delete shortcut on uninstall
    set(CPACK_NSIS_DELETE_ICONS_EXTRA "
        Delete '$DESKTOP\\\\ArchEngine.lnk'
    ")
endif()

# Installation rules
install(TARGETS ArchEngine
    RUNTIME DESTINATION .
    LIBRARY DESTINATION .
    ARCHIVE DESTINATION .
)

# Install ArchEngineLib DLL
install(TARGETS ArchEngineLib
    RUNTIME DESTINATION .
    LIBRARY DESTINATION .
    ARCHIVE DESTINATION .
)

# Install shaders directory
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/shaders/"
    DESTINATION shaders
    FILES_MATCHING PATTERN "*.spv" PATTERN "*.vert" PATTERN "*.frag" PATTERN "*.tesc" PATTERN "*.tese"
)

# Install materials directory
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/materials/"
    DESTINATION materials
)

# Install required DLLs (Windows)
if(WIN32)
    # Install Vulkan runtime DLLs
    if(EXISTS "${VULKAN_SDK}/Runtime/vulkan-1.dll")
        install(FILES
            "${VULKAN_SDK}/Runtime/vulkan-1.dll"
            DESTINATION .
        )
    endif()

    # Install glfw3.dll (will be copied from build directory)
    install(FILES
        "$<TARGET_FILE:glfw>"
        DESTINATION .
    )
endif()

# Install Vulkan runtime installer (if exists)
if(WIN32 AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/dist/vulkan_runtime/VulkanRT-Installer.exe")
    install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/dist/vulkan_runtime/"
        DESTINATION vulkan_runtime
    )
endif()

# Install launcher script
if(WIN32 AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launch_archengine.bat")
    install(FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/launch_archengine.bat"
        DESTINATION .
    )
endif()

# Install README
if(WIN32 AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/README_INSTALL.txt")
    install(FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/README_INSTALL.txt"
        DESTINATION .
        RENAME README.txt
    )
endif()

# Include CPack
include(CPack)
