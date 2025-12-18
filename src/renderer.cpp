#include "renderer.hpp"
#include <stdexcept>
#include <cstring>

namespace arch {


Renderer::Renderer(VulkanContext& context) : m_context(context) {
    createRenderPass();
    createFramebuffers();
    createCommandBuffers();
    createSyncObjects();
    createDescriptorPool();
    createUniformBuffers();
    createDescriptorSets();
    createPipeline();

    // Create grid mesh
    auto [gridVerts, gridIndices] = Geometry::createGrid(100.0f, 5.0f);
    m_gridMesh = std::make_unique<Mesh>(m_context, gridVerts, gridIndices);
}

Renderer::~Renderer() {
    m_context.waitIdle();

    m_gridMesh.reset();
    m_meshCache.clear();
    m_pipeline.reset();
    m_wireframePipeline.reset();

    for (size_t i = 0; i < m_context.getMaxFramesInFlight(); ++i) {
        vkDestroyBuffer(m_context.getDevice(), m_uniformBuffers[i], nullptr);
        vkFreeMemory(m_context.getDevice(), m_uniformBuffersMemory[i], nullptr);
    }

    vkDestroyDescriptorPool(m_context.getDevice(), m_descriptorPool, nullptr);
    vkDestroyDescriptorSetLayout(m_context.getDevice(), m_descriptorSetLayout, nullptr);
    vkDestroyPipelineLayout(m_context.getDevice(), m_pipelineLayout, nullptr);

    for (size_t i = 0; i < m_context.getMaxFramesInFlight(); ++i) {
        vkDestroySemaphore(m_context.getDevice(), m_imageAvailableSemaphores[i], nullptr);
        vkDestroySemaphore(m_context.getDevice(), m_renderFinishedSemaphores[i], nullptr);
        vkDestroyFence(m_context.getDevice(), m_inFlightFences[i], nullptr);
    }

    for (auto fb : m_framebuffers) {
        vkDestroyFramebuffer(m_context.getDevice(), fb, nullptr);
    }

    vkDestroyRenderPass(m_context.getDevice(), m_renderPass, nullptr);
}

void Renderer::createRenderPass() {
    m_renderPass = RenderPassBuilder(m_context)
        .addColorAttachment(m_context.getSwapchainFormat())
        .addDepthAttachment(VK_FORMAT_D32_SFLOAT)
        .addSubpass()
        .build();
}

void Renderer::createFramebuffers() {
    const auto& imageViews = m_context.getSwapchainImageViews();
    auto extent = m_context.getSwapchainExtent();

    m_framebuffers.resize(imageViews.size());

    for (size_t i = 0; i < imageViews.size(); ++i) {
        VkImageView attachments[] = {imageViews[i], m_context.getDepthImageView()};

        VkFramebufferCreateInfo framebufferInfo{};
        framebufferInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        framebufferInfo.renderPass = m_renderPass;
        framebufferInfo.attachmentCount = 2;
        framebufferInfo.pAttachments = attachments;
        framebufferInfo.width = extent.width;
        framebufferInfo.height = extent.height;
        framebufferInfo.layers = 1;

        if (vkCreateFramebuffer(m_context.getDevice(), &framebufferInfo, nullptr,
                                &m_framebuffers[i]) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create framebuffer");
        }
    }
}

void Renderer::createCommandBuffers() {
    m_commandBuffers.resize(m_context.getMaxFramesInFlight());

    VkCommandBufferAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    allocInfo.commandPool = m_context.getCommandPool();
    allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    allocInfo.commandBufferCount = static_cast<u32>(m_commandBuffers.size());

    if (vkAllocateCommandBuffers(m_context.getDevice(), &allocInfo, m_commandBuffers.data()) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate command buffers");
    }
}

void Renderer::createSyncObjects() {
    u32 framesInFlight = m_context.getMaxFramesInFlight();
    m_imageAvailableSemaphores.resize(framesInFlight);
    m_renderFinishedSemaphores.resize(framesInFlight);
    m_inFlightFences.resize(framesInFlight);

    VkSemaphoreCreateInfo semaphoreInfo{};
    semaphoreInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

    VkFenceCreateInfo fenceInfo{};
    fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    fenceInfo.flags = VK_FENCE_CREATE_SIGNALED_BIT;

    for (size_t i = 0; i < framesInFlight; ++i) {
        if (vkCreateSemaphore(m_context.getDevice(), &semaphoreInfo, nullptr, &m_imageAvailableSemaphores[i]) != VK_SUCCESS ||
            vkCreateSemaphore(m_context.getDevice(), &semaphoreInfo, nullptr, &m_renderFinishedSemaphores[i]) != VK_SUCCESS ||
            vkCreateFence(m_context.getDevice(), &fenceInfo, nullptr, &m_inFlightFences[i]) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create sync objects");
        }
    }
}

void Renderer::createDescriptorPool() {
    VkDescriptorPoolSize poolSize{};
    poolSize.type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    poolSize.descriptorCount = m_context.getMaxFramesInFlight();

    VkDescriptorPoolCreateInfo poolInfo{};
    poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    poolInfo.poolSizeCount = 1;
    poolInfo.pPoolSizes = &poolSize;
    poolInfo.maxSets = m_context.getMaxFramesInFlight();

    if (vkCreateDescriptorPool(m_context.getDevice(), &poolInfo, nullptr, &m_descriptorPool) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create descriptor pool");
    }

    VkDescriptorSetLayoutBinding uboBinding{};
    uboBinding.binding = 0;
    uboBinding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    uboBinding.descriptorCount = 1;
    uboBinding.stageFlags = VK_SHADER_STAGE_VERTEX_BIT;

    VkDescriptorSetLayoutCreateInfo layoutInfo{};
    layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layoutInfo.bindingCount = 1;
    layoutInfo.pBindings = &uboBinding;

    if (vkCreateDescriptorSetLayout(m_context.getDevice(), &layoutInfo, nullptr, &m_descriptorSetLayout) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create descriptor set layout");
    }
}

void Renderer::createUniformBuffers() {
    VkDeviceSize bufferSize = sizeof(UniformBufferObject);

    m_uniformBuffers.resize(m_context.getMaxFramesInFlight());
    m_uniformBuffersMemory.resize(m_context.getMaxFramesInFlight());
    m_uniformBuffersMapped.resize(m_context.getMaxFramesInFlight());

    for (size_t i = 0; i < m_context.getMaxFramesInFlight(); ++i) {
        m_context.createBuffer(bufferSize, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
                               VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                               m_uniformBuffers[i], m_uniformBuffersMemory[i]);

        vkMapMemory(m_context.getDevice(), m_uniformBuffersMemory[i], 0, bufferSize, 0, &m_uniformBuffersMapped[i]);
    }
}

void Renderer::createDescriptorSets() {
    std::vector<VkDescriptorSetLayout> layouts(m_context.getMaxFramesInFlight(), m_descriptorSetLayout);

    VkDescriptorSetAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    allocInfo.descriptorPool = m_descriptorPool;
    allocInfo.descriptorSetCount = m_context.getMaxFramesInFlight();
    allocInfo.pSetLayouts = layouts.data();

    m_descriptorSets.resize(m_context.getMaxFramesInFlight());
    if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, m_descriptorSets.data()) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate descriptor sets");
    }

    for (size_t i = 0; i < m_context.getMaxFramesInFlight(); ++i) {
        VkDescriptorBufferInfo bufferInfo{};
        bufferInfo.buffer = m_uniformBuffers[i];
        bufferInfo.offset = 0;
        bufferInfo.range = sizeof(UniformBufferObject);

        VkWriteDescriptorSet descriptorWrite{};
        descriptorWrite.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        descriptorWrite.dstSet = m_descriptorSets[i];
        descriptorWrite.dstBinding = 0;
        descriptorWrite.dstArrayElement = 0;
        descriptorWrite.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        descriptorWrite.descriptorCount = 1;
        descriptorWrite.pBufferInfo = &bufferInfo;

        vkUpdateDescriptorSets(m_context.getDevice(), 1, &descriptorWrite, 0, nullptr);
    }
}

void Renderer::createPipeline() {
    m_pipelineLayout = PipelineLayoutBuilder(m_context)
        .addDescriptorSetLayout(m_descriptorSetLayout)
        .addPushConstantRange(VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(PushConstants))
        .build();

    PipelineConfig config = PipelineConfig::defaultConfig();
    config.renderPass = m_renderPass;
    config.pipelineLayout = m_pipelineLayout;

    m_pipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                             "shaders/structural.frag.spv", config);

    // Wireframe pipeline
    PipelineConfig wireframeConfig = PipelineConfig::defaultConfig();
    wireframeConfig.renderPass = m_renderPass;
    wireframeConfig.pipelineLayout = m_pipelineLayout;
    wireframeConfig.rasterization.polygonMode = VK_POLYGON_MODE_LINE;
    wireframeConfig.rasterization.lineWidth = 1.5f;
    wireframeConfig.rasterization.cullMode = VK_CULL_MODE_NONE;

    m_wireframePipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                      "shaders/structural.frag.spv", wireframeConfig);
}

void Renderer::cleanupSwapchain() {
    for (auto fb : m_framebuffers) {
        vkDestroyFramebuffer(m_context.getDevice(), fb, nullptr);
    }
    m_framebuffers.clear();
}

void Renderer::recreateSwapchain() {
    m_context.waitIdle();
    cleanupSwapchain();
    m_context.recreateSwapchain();
    createFramebuffers();
}

void Renderer::onResize() {
    recreateSwapchain();
}

bool Renderer::beginFrame() {
    vkWaitForFences(m_context.getDevice(), 1, &m_inFlightFences[m_currentFrame], VK_TRUE, UINT64_MAX);

    VkResult result = vkAcquireNextImageKHR(m_context.getDevice(), m_context.getSwapchain(),
                                             UINT64_MAX, m_imageAvailableSemaphores[m_currentFrame],
                                             VK_NULL_HANDLE, &m_imageIndex);

    if (result == VK_ERROR_OUT_OF_DATE_KHR) {
        recreateSwapchain();
        return false;
    } else if (result != VK_SUCCESS && result != VK_SUBOPTIMAL_KHR) {
        throw std::runtime_error("Failed to acquire swap chain image");
    }

    vkResetFences(m_context.getDevice(), 1, &m_inFlightFences[m_currentFrame]);
    vkResetCommandBuffer(m_commandBuffers[m_currentFrame], 0);

    VkCommandBufferBeginInfo beginInfo{};
    beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;

    if (vkBeginCommandBuffer(m_commandBuffers[m_currentFrame], &beginInfo) != VK_SUCCESS) {
        throw std::runtime_error("Failed to begin recording command buffer");
    }

    m_currentCommandBuffer = m_commandBuffers[m_currentFrame];
    m_frameStarted = true;
    m_stats = {};

    updateUniformBuffer(m_currentFrame);

    return true;
}

void Renderer::endFrame() {
    if (vkEndCommandBuffer(m_currentCommandBuffer) != VK_SUCCESS) {
        throw std::runtime_error("Failed to record command buffer");
    }

    VkSubmitInfo submitInfo{};
    submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;

    VkSemaphore waitSemaphores[] = {m_imageAvailableSemaphores[m_currentFrame]};
    VkPipelineStageFlags waitStages[] = {VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT};
    submitInfo.waitSemaphoreCount = 1;
    submitInfo.pWaitSemaphores = waitSemaphores;
    submitInfo.pWaitDstStageMask = waitStages;
    submitInfo.commandBufferCount = 1;
    submitInfo.pCommandBuffers = &m_commandBuffers[m_currentFrame];

    VkSemaphore signalSemaphores[] = {m_renderFinishedSemaphores[m_currentFrame]};
    submitInfo.signalSemaphoreCount = 1;
    submitInfo.pSignalSemaphores = signalSemaphores;

    if (vkQueueSubmit(m_context.getGraphicsQueue(), 1, &submitInfo, m_inFlightFences[m_currentFrame]) != VK_SUCCESS) {
        throw std::runtime_error("Failed to submit draw command buffer");
    }

    VkPresentInfoKHR presentInfo{};
    presentInfo.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
    presentInfo.waitSemaphoreCount = 1;
    presentInfo.pWaitSemaphores = signalSemaphores;

    VkSwapchainKHR swapchains[] = {m_context.getSwapchain()};
    presentInfo.swapchainCount = 1;
    presentInfo.pSwapchains = swapchains;
    presentInfo.pImageIndices = &m_imageIndex;

    VkResult result = vkQueuePresentKHR(m_context.getPresentQueue(), &presentInfo);

    if (result == VK_ERROR_OUT_OF_DATE_KHR || result == VK_SUBOPTIMAL_KHR) {
        recreateSwapchain();
    } else if (result != VK_SUCCESS) {
        throw std::runtime_error("Failed to present swap chain image");
    }

    m_currentFrame = (m_currentFrame + 1) % m_context.getMaxFramesInFlight();
    m_frameStarted = false;
    m_time += 0.016f;
}

void Renderer::beginRenderPass(vec4 clearColor) {
    VkRenderPassBeginInfo renderPassInfo{};
    renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    renderPassInfo.renderPass = m_renderPass;
    renderPassInfo.framebuffer = m_framebuffers[m_imageIndex];
    renderPassInfo.renderArea.offset = {0, 0};
    renderPassInfo.renderArea.extent = m_context.getSwapchainExtent();

    VkClearValue clearValues[2];
    clearValues[0].color = {{clearColor.r, clearColor.g, clearColor.b, clearColor.a}};
    clearValues[1].depthStencil = {1.0f, 0};

    renderPassInfo.clearValueCount = 2;
    renderPassInfo.pClearValues = clearValues;

    vkCmdBeginRenderPass(m_currentCommandBuffer, &renderPassInfo, VK_SUBPASS_CONTENTS_INLINE);

    auto extent = m_context.getSwapchainExtent();
    VkViewport viewport{};
    viewport.x = 0.0f;
    viewport.y = 0.0f;
    viewport.width = static_cast<f32>(extent.width);
    viewport.height = static_cast<f32>(extent.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;
    vkCmdSetViewport(m_currentCommandBuffer, 0, 1, &viewport);

    VkRect2D scissor{};
    scissor.offset = {0, 0};
    scissor.extent = extent;
    vkCmdSetScissor(m_currentCommandBuffer, 0, 1, &scissor);

    // Bind appropriate pipeline based on visualization mode
    if (m_vizMode == VisualizationMode::Wireframe) {
        m_wireframePipeline->bind(m_currentCommandBuffer);
    } else {
        m_pipeline->bind(m_currentCommandBuffer);
    }
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, 1, &m_descriptorSets[m_currentFrame], 0, nullptr);
}

void Renderer::endRenderPass() {
    vkCmdEndRenderPass(m_currentCommandBuffer);
}

void Renderer::setCamera(const Camera& camera) {
    m_camera = camera;
}

void Renderer::updateUniformBuffer(u32 frameIndex) {
    auto extent = m_context.getSwapchainExtent();

    f32 aspectRatio = static_cast<f32>(extent.width) / static_cast<f32>(extent.height);
    
    UniformBufferObject ubo{};
    ubo.view = m_camera.getViewMatrix();
    ubo.proj = m_camera.getProjectionMatrix(aspectRatio);
    ubo.proj[1][1] *= -1;
    ubo.time = m_time;

    std::memcpy(m_uniformBuffersMapped[frameIndex], &ubo, sizeof(ubo));
}

vec3 Renderer::getElementColor(const StructuralElement& element, const Building& building, size_t index) const {
    std::string elemKey = "elem_" + std::to_string(index);
    
    switch (m_vizMode) {
        case VisualizationMode::Structural:
            return StressColors::fromStress(element.stress);
            
        case VisualizationMode::Thermal: {
            auto it = building.thermalData.find(elemKey);
            if (it != building.thermalData.end()) {
                return ThermalColors::fromTemperature(it->second.temperature);
            }
            f32 height = (element.start.y + element.end.y) * 0.5f;
            f32 temp = 65.0f + height * 0.5f;
            return ThermalColors::fromTemperature(temp);
        }
        
        case VisualizationMode::Lighting: {
            auto it = building.lightingData.find(elemKey);
            if (it != building.lightingData.end()) {
                return LightingColors::fromLux(it->second.illuminanceLux);
            }
            f32 distFromEdge = glm::min(element.start.x, element.start.z);
            f32 lux = 800.0f * glm::exp(-distFromEdge * 0.05f);
            return LightingColors::fromLux(lux);
        }
        
        case VisualizationMode::Acoustic: {
            auto it = building.acousticData.find(elemKey);
            if (it != building.acousticData.end()) {
                return AcousticColors::fromRT60(it->second.rt60);
            }
            f32 volume = glm::length(element.end - element.start) * element.width * element.depth;
            f32 rt60 = 0.161f * volume / 50.0f;
            return AcousticColors::fromRT60(rt60);
        }
        
        case VisualizationMode::Material: {
            if (element.material == "steel") return vec3(0.6f, 0.65f, 0.7f);
            if (element.material == "concrete") return vec3(0.5f, 0.5f, 0.5f);
            if (element.material == "wood") return vec3(0.65f, 0.45f, 0.25f);
            if (element.material == "glass") return vec3(0.6f, 0.8f, 0.9f);
            if (element.material == "brick") return vec3(0.7f, 0.35f, 0.2f);
            if (element.material == "aluminum") return vec3(0.75f, 0.75f, 0.8f);
            if (element.material == "door") return vec3(0.55f, 0.35f, 0.15f);
            if (element.material == "window") return vec3(0.6f, 0.8f, 0.9f);
            if (element.material == "roof") return vec3(0.4f, 0.35f, 0.35f);
            if (element.material == "shingle") return vec3(0.3f, 0.3f, 0.3f);
            if (element.material == "tile") return vec3(0.7f, 0.3f, 0.2f);
            return vec3(0.5f, 0.5f, 0.5f);
        }
        
        case VisualizationMode::Wireframe:
            return vec3(0.2f, 0.8f, 0.4f);
            
        default:
            return StressColors::fromStress(element.stress);
    }
}

void Renderer::drawMesh(Mesh& mesh, const mat4& transform, vec3 color, f32 stress) {
    PushConstants push{};
    push.model = transform;
    push.color = vec4(color, stress);  // stress in alpha controls shader behavior

    vkCmdPushConstants(m_currentCommandBuffer, m_pipelineLayout,
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT,
                       0, sizeof(PushConstants), &push);

    mesh.bind(m_currentCommandBuffer);
    mesh.draw(m_currentCommandBuffer);

    m_stats.drawCalls++;
    m_stats.triangles += mesh.getIndexCount() / 3;
}

void Renderer::drawBeam(vec3 start, vec3 end, f32 width, f32 height, vec3 color, f32 stress, f32 deflection) {
    std::string key = "beam_" + std::to_string(glm::length(end - start)) + "_" +
                      std::to_string(width) + "_" + std::to_string(height);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = (deflection > 0.001f) ?
            Geometry::createDeflectedBeam(vec3(0), vec3(glm::length(end - start), 0, 0),
                                          width, height, deflection, 16, color) :
            Geometry::createBeam(vec3(0), vec3(glm::length(end - start), 0, 0),
                                width, height, color);

        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    vec3 dir = glm::normalize(end - start);
    vec3 up = vec3(0, 1, 0);
    if (std::abs(glm::dot(dir, up)) > 0.99f) {
        up = vec3(0, 0, 1);
    }

    mat4 transform = glm::translate(mat4(1.0f), start);

    vec3 right = glm::normalize(glm::cross(up, dir));
    vec3 localUp = glm::cross(dir, right);
    mat4 rotation(1.0f);
    rotation[0] = vec4(dir, 0);
    rotation[1] = vec4(localUp, 0);
    rotation[2] = vec4(right, 0);
    transform = transform * rotation;

    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawColumn(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress) {
    std::string key = "col_" + std::to_string(width) + "_" + std::to_string(depth) + "_" + std::to_string(height);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createColumn(vec3(0), width, depth, height, color);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawFloor(vec3 position, f32 width, f32 depth, f32 thickness, vec3 color, f32 stress) {
    std::string key = "floor_" + std::to_string(width) + "_" + std::to_string(depth) + "_" + std::to_string(thickness);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createFloorSlab(vec3(0), width, depth, thickness);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawDoor(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress) {
    std::string key = "door_" + std::to_string(width) + "_" + std::to_string(height) + "_" + std::to_string(depth);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createDoor(vec3(0), width, height, depth, color);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawWindow(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress) {
    std::string key = "window_" + std::to_string(width) + "_" + std::to_string(height) + "_" + std::to_string(depth);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createWindow(vec3(0), width, height, depth, color);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawRoof(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress) {
    // Use a standard roof pitch (rise/run ratio) - 0.5 = 6:12 pitch
    f32 pitch = 0.5f;
    std::string key = "roof_" + std::to_string(width) + "_" + std::to_string(depth) + "_" + std::to_string(height) + "_pitched";

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createRoof(vec3(0), width, depth, height, pitch, color);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawCustomMesh(const MeshData& meshData, vec3 color, f32 stress) {
    if (!meshData.hasData()) return;

    // Create unique key based on mesh data hash
    size_t hash = 0;
    for (const auto& v : meshData.vertices) {
        hash ^= std::hash<float>{}(v.x) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
        hash ^= std::hash<float>{}(v.y) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
        hash ^= std::hash<float>{}(v.z) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
    }
    std::string key = "custom_" + std::to_string(hash);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        // Convert MeshData to vertices with normals
        std::vector<Vertex> vertices;
        std::vector<u32> indices;

        // Build vertices and compute normals per-face
        for (const auto& face : meshData.faces) {
            // Get the three vertices of this face
            const vec3& v0 = meshData.vertices[face[0]];
            const vec3& v1 = meshData.vertices[face[1]];
            const vec3& v2 = meshData.vertices[face[2]];

            // Compute face normal
            vec3 edge1 = v1 - v0;
            vec3 edge2 = v2 - v0;
            vec3 normal = glm::normalize(glm::cross(edge1, edge2));

            // Add vertices with face normal (flat shading)
            u32 baseIndex = static_cast<u32>(vertices.size());
            vertices.push_back({v0, normal, color});
            vertices.push_back({v1, normal, color});
            vertices.push_back({v2, normal, color});

            indices.push_back(baseIndex + 0);
            indices.push_back(baseIndex + 1);
            indices.push_back(baseIndex + 2);
        }

        m_meshCache[key] = std::make_unique<Mesh>(m_context, vertices, indices);
    }

    mat4 transform = mat4(1.0f);  // Identity - vertices are already in world space
    drawMesh(*m_meshCache[key], transform, color, stress);
}

void Renderer::drawGrid(f32 size, f32 spacing) {
    (void)size; (void)spacing;
    mat4 transform = mat4(1.0f);
    PushConstants push{};
    push.model = transform;
    push.color = vec4(0.3f, 0.3f, 0.3f, 1.0f);

    vkCmdPushConstants(m_currentCommandBuffer, m_pipelineLayout,
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT,
                       0, sizeof(PushConstants), &push);

    m_gridMesh->bind(m_currentCommandBuffer);
    m_gridMesh->draw(m_currentCommandBuffer);

    m_stats.drawCalls++;
}

void Renderer::drawLoadArrow(vec3 start, vec3 end, f32 magnitude) {
    (void)magnitude;
    std::string key = "arrow_" + std::to_string(glm::length(end - start));

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createArrow(vec3(0), vec3(0, -glm::length(end - start), 0));
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), start);
    drawMesh(*m_meshCache[key], transform, vec3(1.0f, 0.0f, 0.0f));
}

void Renderer::drawStructuralFrame(const std::vector<StructuralElement>& elements, const Building& building, const std::set<int>& selectedIndices) {
    m_context.beginDebugLabel(m_currentCommandBuffer, "Structural Frame", {0.2f, 0.6f, 0.9f, 1.0f});

    size_t index = 0;
    for (const auto& element : elements) {
        vec3 color = getElementColor(element, building, index);

        // Highlight selected elements with yellow/orange
        bool isSelected = selectedIndices.count(static_cast<int>(index)) > 0;
        if (isSelected) {
            color = vec3(1.0f, 0.8f, 0.2f);  // Yellow-orange highlight
        }
        // Only pass stress to shader for Structural mode; otherwise pass 0 so shader uses RGB color
        f32 stressForShader = (m_vizMode == VisualizationMode::Structural) ? element.stress : 0.0f;
        
        switch (element.type) {
            case ElementType::Beam:
                drawBeam(element.start, element.end, element.width, element.depth,
                        color, stressForShader, element.deflection);
                break;

            case ElementType::Column:
                drawColumn(element.start, element.width, element.depth,
                          element.end.y - element.start.y, color, stressForShader);
                break;

            case ElementType::Floor: {
                // Use IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry
                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;
                    drawFloor(center,
                             element.end.x - element.start.x,
                             element.end.z - element.start.z,
                             element.depth, color, stressForShader);
                }
                break;
            }

            case ElementType::Wall: {
                // Use custom mesh if available (e.g., gable wall)
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated box geometry
                    // Determine wall orientation from extents
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float height = element.end.y - element.start.y;

                    // Calculate center point (drawColumn centers geometry on position)
                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;  // Keep base at start height

                    if (std::abs(xExtent) >= std::abs(zExtent)) {
                        // Wall runs along X axis
                        drawColumn(center, xExtent, zExtent, height, color, stressForShader);
                    } else {
                        // Wall runs along Z axis
                        drawColumn(center, xExtent, zExtent, height, color, stressForShader);
                    }
                }
                break;
            }

            case ElementType::Door: {
                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float doorHeight = element.end.y - element.start.y;

                    float doorWidth = std::max(std::abs(xExtent), std::abs(zExtent));
                    float doorDepth = std::min(std::abs(xExtent), std::abs(zExtent));
                    if (doorDepth < 0.1f) doorDepth = element.depth;

                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;

                    drawDoor(center, doorWidth, doorHeight, doorDepth, color, stressForShader);
                }
                break;
            }

            case ElementType::Window: {
                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float windowHeight = element.end.y - element.start.y;

                    float windowWidth = std::max(std::abs(xExtent), std::abs(zExtent));
                    float windowDepth = std::min(std::abs(xExtent), std::abs(zExtent));
                    if (windowDepth < 0.1f) windowDepth = element.depth;

                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;

                    drawWindow(center, windowWidth, windowHeight, windowDepth, color, stressForShader);
                }
                break;
            }

            case ElementType::Roof: {
                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry
                    float roofWidth = std::abs(element.end.x - element.start.x);
                    float roofDepthZ = std::abs(element.end.z - element.start.z);
                    float roofThickness = element.end.y - element.start.y;
                    if (roofThickness < 0.1f) roofThickness = 0.5f;

                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;

                    drawRoof(center, roofWidth, roofDepthZ, roofThickness, color, stressForShader);
                }
                break;
            }

            default:
                break;
        }
        index++;
    }

    m_context.endDebugLabel(m_currentCommandBuffer);
}

} // namespace arch
