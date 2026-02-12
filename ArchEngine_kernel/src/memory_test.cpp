#include "memory_test.hpp"
#include <iostream>
#include <chrono>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif

namespace arch {

size_t MemoryTest::getCurrentMemoryUsage() {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS_EX pmc;
    if (GetProcessMemoryInfo(GetCurrentProcess(), (PROCESS_MEMORY_COUNTERS*)&pmc, sizeof(pmc))) {
        return pmc.WorkingSetSize;
    }
#endif
    return 0;
}

void MemoryTest::logMemory(const std::string& label) {
    size_t mem = getCurrentMemoryUsage();
    std::cout << "[MemTest] " << label << ": " << (mem / (1024 * 1024)) << " MB" << std::endl;
}

MemoryTestResult MemoryTest::runAllTests(VulkanContext& context, Renderer& renderer) {
    MemoryTestResult result;
    result.passed = true;

    std::cout << "\n========== MEMORY LEAK TEST ==========\n" << std::endl;

    size_t startMem = getCurrentMemoryUsage();
    logMemory("Initial");

    // Test 1: Mesh creation/destruction cycles
    {
        std::cout << "\n[Test 1] Mesh allocation cycles..." << std::endl;
        size_t beforeTest = getCurrentMemoryUsage();

        for (int cycle = 0; cycle < 10; cycle++) {
            std::vector<std::unique_ptr<Mesh>> meshes;

            // Create 100 meshes
            for (int i = 0; i < 100; i++) {
                std::vector<Vertex> verts(3);
                verts[0] = {vec3(0, 0, 0), vec3(0, 0, 1), vec3(1, 1, 1), vec2(0, 0), 0.0f};
                verts[1] = {vec3(1, 0, 0), vec3(0, 0, 1), vec3(1, 1, 1), vec2(1, 0), 0.0f};
                verts[2] = {vec3(0, 1, 0), vec3(0, 0, 1), vec3(1, 1, 1), vec2(0, 1), 0.0f};
                std::vector<u32> indices = {0, 1, 2};
                meshes.push_back(std::make_unique<Mesh>(context, verts, indices));
            }

            // Destroy all meshes (automatic via unique_ptr)
            meshes.clear();
        }

        // Wait for GPU to finish
        context.waitIdle();

        size_t afterTest = getCurrentMemoryUsage();
        int64_t diff = static_cast<int64_t>(afterTest) - static_cast<int64_t>(beforeTest);

        std::cout << "  Before: " << (beforeTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  After:  " << (afterTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  Diff:   " << (diff / 1024) << " KB" << std::endl;

        // Allow some variance (< 5MB growth is acceptable due to fragmentation)
        if (diff > 5 * 1024 * 1024) {
            std::cout << "  POTENTIAL LEAK: Mesh resources" << std::endl;
            result.meshLeakDetected = true;
            result.passed = false;
        } else {
            std::cout << "  PASSED" << std::endl;
        }
    }

    // Test 2: Texture creation/destruction cycles
    {
        std::cout << "\n[Test 2] Texture allocation cycles..." << std::endl;
        size_t beforeTest = getCurrentMemoryUsage();

        for (int cycle = 0; cycle < 5; cycle++) {
            std::vector<std::unique_ptr<Texture>> textures;

            // Create 20 solid color textures
            for (int i = 0; i < 20; i++) {
                auto tex = std::make_unique<Texture>(context);
                tex->createSolidColor(vec4(0.5f, 0.5f, 0.5f, 1.0f));
                textures.push_back(std::move(tex));
            }

            // Destroy all
            textures.clear();
        }

        context.waitIdle();

        size_t afterTest = getCurrentMemoryUsage();
        int64_t diff = static_cast<int64_t>(afterTest) - static_cast<int64_t>(beforeTest);

        std::cout << "  Before: " << (beforeTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  After:  " << (afterTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  Diff:   " << (diff / 1024) << " KB" << std::endl;

        if (diff > 10 * 1024 * 1024) {
            std::cout << "  POTENTIAL LEAK: Texture resources" << std::endl;
            result.textureLeakDetected = true;
            result.passed = false;
        } else {
            std::cout << "  PASSED" << std::endl;
        }
    }

    // Test 3: Pipeline creation/destruction
    {
        std::cout << "\n[Test 3] Pipeline allocation cycles..." << std::endl;
        size_t beforeTest = getCurrentMemoryUsage();

        // Get render pass from renderer for pipeline creation
        VkRenderPass renderPass = renderer.getRenderPass();
        VkPipelineLayout pipelineLayout = renderer.getPipelineLayout();

        for (int cycle = 0; cycle < 5; cycle++) {
            std::vector<std::unique_ptr<Pipeline>> pipelines;

            // Create 5 pipelines
            for (int i = 0; i < 5; i++) {
                PipelineConfig config = PipelineConfig::defaultConfig();
                config.renderPass = renderPass;
                config.pipelineLayout = pipelineLayout;
                config.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

                pipelines.push_back(std::make_unique<Pipeline>(
                    context,
                    "shaders/structural.vert.spv",
                    "shaders/structural.frag.spv",
                    config
                ));
            }

            // Destroy all
            pipelines.clear();
        }

        context.waitIdle();

        size_t afterTest = getCurrentMemoryUsage();
        int64_t diff = static_cast<int64_t>(afterTest) - static_cast<int64_t>(beforeTest);

        std::cout << "  Before: " << (beforeTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  After:  " << (afterTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  Diff:   " << (diff / 1024) << " KB" << std::endl;

        if (diff > 5 * 1024 * 1024) {
            std::cout << "  POTENTIAL LEAK: Pipeline resources" << std::endl;
            result.pipelineLeakDetected = true;
            result.passed = false;
        } else {
            std::cout << "  PASSED" << std::endl;
        }
    }

    // Test 4: HDR toggle stress test
    {
        std::cout << "\n[Test 4] HDR toggle stress test..." << std::endl;
        size_t beforeTest = getCurrentMemoryUsage();

        for (int cycle = 0; cycle < 20; cycle++) {
            renderer.setPostProcessingEnabled(true);
            renderer.setPostProcessingEnabled(false);
        }

        context.waitIdle();

        size_t afterTest = getCurrentMemoryUsage();
        int64_t diff = static_cast<int64_t>(afterTest) - static_cast<int64_t>(beforeTest);

        std::cout << "  Before: " << (beforeTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  After:  " << (afterTest / (1024 * 1024)) << " MB" << std::endl;
        std::cout << "  Diff:   " << (diff / 1024) << " KB" << std::endl;

        if (diff > 2 * 1024 * 1024) {
            std::cout << "  POTENTIAL LEAK: HDR toggle" << std::endl;
            result.hdrLeakDetected = true;
            result.passed = false;
        } else {
            std::cout << "  PASSED" << std::endl;
        }
    }

    // Final summary
    size_t endMem = getCurrentMemoryUsage();
    int64_t totalDiff = static_cast<int64_t>(endMem) - static_cast<int64_t>(startMem);

    std::cout << "\n========== SUMMARY ==========" << std::endl;
    std::cout << "Start memory:  " << (startMem / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "End memory:    " << (endMem / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "Total change:  " << (totalDiff / 1024) << " KB" << std::endl;

    result.startMemory = startMem;
    result.endMemory = endMem;
    result.memoryDelta = totalDiff;

    if (result.passed) {
        std::cout << "\nRESULT: ALL TESTS PASSED" << std::endl;
    } else {
        std::cout << "\nRESULT: LEAKS DETECTED" << std::endl;
    }
    std::cout << "==============================\n" << std::endl;

    return result;
}

} // namespace arch
