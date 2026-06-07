# Tests for ArchGeometry library
cmake_minimum_required(VERSION 3.14)

# Fetch Google Test
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
# Prevent overriding parent project's compiler/linker settings on Windows
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# Enable testing
include(GoogleTest)

# Test executable
add_executable(archgeometry_tests
    test_schema_parser.cpp
    test_wall_geometry.cpp
    test_floor_geometry.cpp
    test_query_api.cpp
)

target_link_libraries(archgeometry_tests
    PRIVATE
        archgeometry
        GTest::gtest_main
)

# Register tests
gtest_discover_tests(archgeometry_tests)
