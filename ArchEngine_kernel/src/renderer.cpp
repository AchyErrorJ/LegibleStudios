#include "renderer.hpp"
#include <stdexcept>
#include <cstring>
#include <array>

namespace arch {


Renderer::Renderer(VulkanContext& context) : m_context(context) {
    createRenderPass();
    createFramebuffers();
    createCommandBuffers();
    createSyncObjects();

    // Create shadow map BEFORE descriptor sets so it can be bound
    if (m_context.getConfig().enableShadows) {
        m_shadowMap = std::make_unique<ShadowMap>(m_context, m_context.getConfig().shadowMapResolution);
    }

    // Create environment map (procedural sky by default)
    m_envMap = std::make_unique<EnvironmentMap>(m_context);
    m_envMap->createProceduralSky();

    // Create post-processing pipeline (SSAO, bloom, etc.)
    m_postProcess = std::make_unique<PostProcess>(m_context);
    auto extent = m_context.getSwapchainExtent();
    m_postProcess->initialize(extent.width, extent.height);

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

#if 0  // Ray tracing disabled - incomplete implementation
    // Cleanup ray tracing resources
    m_rtPipeline.reset();
    m_accelStructManager.reset();
    m_rtVertexBuffer.destroy(m_context.getDevice());
    m_rtIndexBuffer.destroy(m_context.getDevice());
    m_rtMaterialBuffer.destroy(m_context.getDevice());
#endif

    m_postProcess.reset();
    m_envMap.reset();
    m_shadowMap.reset();
    m_gridMesh.reset();
    m_meshCache.clear();
    m_pipeline.reset();
    m_wireframePipeline.reset();

    for (size_t i = 0; i < m_context.getSwapchainImageCount(); ++i) {
        vkDestroyBuffer(m_context.getDevice(), m_uniformBuffers[i], nullptr);
        vkFreeMemory(m_context.getDevice(), m_uniformBuffersMemory[i], nullptr);
    }

    vkDestroyDescriptorPool(m_context.getDevice(), m_descriptorPool, nullptr);
    vkDestroyDescriptorSetLayout(m_context.getDevice(), m_descriptorSetLayout, nullptr);
    vkDestroyPipelineLayout(m_context.getDevice(), m_pipelineLayout, nullptr);

    // Cleanup sky pipeline
    if (m_skyPipeline != VK_NULL_HANDLE) {
        vkDestroyPipeline(m_context.getDevice(), m_skyPipeline, nullptr);
    }
    if (m_skyPipelineLayout != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(m_context.getDevice(), m_skyPipelineLayout, nullptr);
    }
    if (m_skyDescriptorSetLayout != VK_NULL_HANDLE) {
        vkDestroyDescriptorSetLayout(m_context.getDevice(), m_skyDescriptorSetLayout, nullptr);
    }

    // Destroy per-frame-in-flight sync objects
    for (size_t i = 0; i < m_context.getMaxFramesInFlight(); ++i) {
        vkDestroySemaphore(m_context.getDevice(), m_imageAvailableSemaphores[i], nullptr);
        vkDestroyFence(m_context.getDevice(), m_inFlightFences[i], nullptr);
    }

    // Destroy per-swapchain-image semaphores
    for (size_t i = 0; i < m_renderFinishedSemaphores.size(); ++i) {
        vkDestroySemaphore(m_context.getDevice(), m_renderFinishedSemaphores[i], nullptr);
    }

    for (auto fb : m_framebuffers) {
        vkDestroyFramebuffer(m_context.getDevice(), fb, nullptr);
    }

    vkDestroyRenderPass(m_context.getDevice(), m_renderPass, nullptr);
}

void Renderer::createRenderPass() {
    VkSampleCountFlagBits msaaSamples = m_context.getMsaaSamples();
    bool useMsaa = msaaSamples != VK_SAMPLE_COUNT_1_BIT;

    std::vector<VkAttachmentDescription> attachments;
    
    if (useMsaa) {
        // Attachment 0: MSAA color buffer (multisampled)
        VkAttachmentDescription colorAttachment{};
        colorAttachment.format = m_context.getSwapchainFormat();
        colorAttachment.samples = msaaSamples;
        colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
        colorAttachment.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        colorAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        colorAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        colorAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        colorAttachment.finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        attachments.push_back(colorAttachment);

        // Attachment 1: Resolve target (swapchain image)
        VkAttachmentDescription resolveAttachment{};
        resolveAttachment.format = m_context.getSwapchainFormat();
        resolveAttachment.samples = VK_SAMPLE_COUNT_1_BIT;
        resolveAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        resolveAttachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        resolveAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        resolveAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        resolveAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        resolveAttachment.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        attachments.push_back(resolveAttachment);

        // Attachment 2: MSAA depth buffer
        VkAttachmentDescription depthAttachment{};
        depthAttachment.format = VK_FORMAT_D32_SFLOAT;
        depthAttachment.samples = msaaSamples;
        depthAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
        depthAttachment.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        depthAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        depthAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        depthAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        depthAttachment.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
        attachments.push_back(depthAttachment);

        // Subpass references
        VkAttachmentReference colorRef{0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
        VkAttachmentReference resolveRef{1, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
        VkAttachmentReference depthRef{2, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL};

        VkSubpassDescription subpass{};
        subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
        subpass.colorAttachmentCount = 1;
        subpass.pColorAttachments = &colorRef;
        subpass.pResolveAttachments = &resolveRef;
        subpass.pDepthStencilAttachment = &depthRef;

        VkSubpassDependency dependency{};
        dependency.srcSubpass = VK_SUBPASS_EXTERNAL;
        dependency.dstSubpass = 0;
        dependency.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
        dependency.srcAccessMask = 0;
        dependency.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
        dependency.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

        VkRenderPassCreateInfo renderPassInfo{};
        renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
        renderPassInfo.attachmentCount = static_cast<u32>(attachments.size());
        renderPassInfo.pAttachments = attachments.data();
        renderPassInfo.subpassCount = 1;
        renderPassInfo.pSubpasses = &subpass;
        renderPassInfo.dependencyCount = 1;
        renderPassInfo.pDependencies = &dependency;

        if (vkCreateRenderPass(m_context.getDevice(), &renderPassInfo, nullptr, &m_renderPass) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create MSAA render pass");
        }
    } else {
        // Non-MSAA path using RenderPassBuilder
        m_renderPass = RenderPassBuilder(m_context)
            .addColorAttachment(m_context.getSwapchainFormat())
            .addDepthAttachment(VK_FORMAT_D32_SFLOAT)
            .addSubpass()
            .build();
    }
}

void Renderer::createFramebuffers() {
    const auto& imageViews = m_context.getSwapchainImageViews();
    auto extent = m_context.getSwapchainExtent();
    VkSampleCountFlagBits msaaSamples = m_context.getMsaaSamples();
    bool useMsaa = msaaSamples != VK_SAMPLE_COUNT_1_BIT;

    m_framebuffers.resize(imageViews.size());

    for (size_t i = 0; i < imageViews.size(); ++i) {
        std::vector<VkImageView> attachments;
        
        if (useMsaa) {
            // MSAA: 3 attachments - MSAA color, resolve target (swapchain), MSAA depth
            attachments = {
                m_context.getMsaaColorImageView(),  // MSAA color
                imageViews[i],                       // Resolve target
                m_context.getDepthImageView()        // MSAA depth
            };
        } else {
            // No MSAA: 2 attachments - color, depth
            attachments = {
                imageViews[i],
                m_context.getDepthImageView()
            };
        }

        VkFramebufferCreateInfo framebufferInfo{};
        framebufferInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
        framebufferInfo.renderPass = m_renderPass;
        framebufferInfo.attachmentCount = static_cast<u32>(attachments.size());
        framebufferInfo.pAttachments = attachments.data();
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
    // One command buffer per swapchain image
    m_commandBuffers.resize(m_context.getSwapchainImageCount());

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
    u32 maxFrames = m_context.getMaxFramesInFlight();
    u32 imageCount = m_context.getSwapchainImageCount();

    // Per-frame-in-flight: semaphores for acquiring images, fences for CPU-GPU sync
    m_imageAvailableSemaphores.resize(maxFrames);
    m_inFlightFences.resize(maxFrames);

    // Per-swapchain-image: semaphores for presentation (must match acquired image)
    m_renderFinishedSemaphores.resize(imageCount);

    // Track which fence is using each swapchain image
    m_imagesInFlight.resize(imageCount, VK_NULL_HANDLE);

    VkSemaphoreCreateInfo semaphoreInfo{};
    semaphoreInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

    VkFenceCreateInfo fenceInfo{};
    fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    fenceInfo.flags = VK_FENCE_CREATE_SIGNALED_BIT;

    for (size_t i = 0; i < maxFrames; ++i) {
        if (vkCreateSemaphore(m_context.getDevice(), &semaphoreInfo, nullptr, &m_imageAvailableSemaphores[i]) != VK_SUCCESS ||
            vkCreateFence(m_context.getDevice(), &fenceInfo, nullptr, &m_inFlightFences[i]) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create sync objects");
        }
    }

    // Create per-image render finished semaphores
    for (size_t i = 0; i < imageCount; ++i) {
        if (vkCreateSemaphore(m_context.getDevice(), &semaphoreInfo, nullptr, &m_renderFinishedSemaphores[i]) != VK_SUCCESS) {
            throw std::runtime_error("Failed to create render finished semaphores");
        }
    }
}

void Renderer::createDescriptorPool() {
    std::vector<VkDescriptorPoolSize> poolSizes;

    u32 imageCount = m_context.getSwapchainImageCount();

    // UBO pool size (main pipeline + sky pipeline)
    VkDescriptorPoolSize uboPoolSize{};
    uboPoolSize.type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    uboPoolSize.descriptorCount = imageCount * 2;  // main + sky
    poolSizes.push_back(uboPoolSize);

    // Sampler pool size (shadow map + environment cubemap)
    VkDescriptorPoolSize samplerPoolSize{};
    samplerPoolSize.type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    samplerPoolSize.descriptorCount = imageCount * 2;  // shadow + envmap
    poolSizes.push_back(samplerPoolSize);

    VkDescriptorPoolCreateInfo poolInfo{};
    poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    poolInfo.poolSizeCount = static_cast<u32>(poolSizes.size());
    poolInfo.pPoolSizes = poolSizes.data();
    poolInfo.maxSets = imageCount * 2;  // main + sky descriptor sets

    if (vkCreateDescriptorPool(m_context.getDevice(), &poolInfo, nullptr, &m_descriptorPool) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create descriptor pool");
    }

    std::vector<VkDescriptorSetLayoutBinding> bindings;

    // Binding 0: UBO
    VkDescriptorSetLayoutBinding uboBinding{};
    uboBinding.binding = 0;
    uboBinding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    uboBinding.descriptorCount = 1;
    uboBinding.stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT;
    bindings.push_back(uboBinding);

    // Binding 1: Shadow map sampler (if shadows enabled)
    if (m_shadowMap) {
        VkDescriptorSetLayoutBinding shadowBinding{};
        shadowBinding.binding = 1;
        shadowBinding.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        shadowBinding.descriptorCount = 1;
        shadowBinding.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;
        bindings.push_back(shadowBinding);
    }

    VkDescriptorSetLayoutCreateInfo layoutInfo{};
    layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layoutInfo.bindingCount = static_cast<u32>(bindings.size());
    layoutInfo.pBindings = bindings.data();

    if (vkCreateDescriptorSetLayout(m_context.getDevice(), &layoutInfo, nullptr, &m_descriptorSetLayout) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create descriptor set layout");
    }
}

void Renderer::createUniformBuffers() {
    VkDeviceSize bufferSize = sizeof(UniformBufferObject);

    m_uniformBuffers.resize(m_context.getSwapchainImageCount());
    m_uniformBuffersMemory.resize(m_context.getSwapchainImageCount());
    m_uniformBuffersMapped.resize(m_context.getSwapchainImageCount());

    for (size_t i = 0; i < m_context.getSwapchainImageCount(); ++i) {
        m_context.createBuffer(bufferSize, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
                               VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                               m_uniformBuffers[i], m_uniformBuffersMemory[i]);

        vkMapMemory(m_context.getDevice(), m_uniformBuffersMemory[i], 0, bufferSize, 0, &m_uniformBuffersMapped[i]);
    }
}

void Renderer::createDescriptorSets() {
    std::vector<VkDescriptorSetLayout> layouts(m_context.getSwapchainImageCount(), m_descriptorSetLayout);

    VkDescriptorSetAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    allocInfo.descriptorPool = m_descriptorPool;
    allocInfo.descriptorSetCount = m_context.getSwapchainImageCount();
    allocInfo.pSetLayouts = layouts.data();

    m_descriptorSets.resize(m_context.getSwapchainImageCount());
    if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, m_descriptorSets.data()) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate descriptor sets");
    }

    for (size_t i = 0; i < m_context.getSwapchainImageCount(); ++i) {
        std::vector<VkWriteDescriptorSet> descriptorWrites;

        // UBO write
        VkDescriptorBufferInfo bufferInfo{};
        bufferInfo.buffer = m_uniformBuffers[i];
        bufferInfo.offset = 0;
        bufferInfo.range = sizeof(UniformBufferObject);

        VkWriteDescriptorSet uboWrite{};
        uboWrite.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        uboWrite.dstSet = m_descriptorSets[i];
        uboWrite.dstBinding = 0;
        uboWrite.dstArrayElement = 0;
        uboWrite.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        uboWrite.descriptorCount = 1;
        uboWrite.pBufferInfo = &bufferInfo;
        descriptorWrites.push_back(uboWrite);

        // Shadow map write (if shadows enabled)
        VkDescriptorImageInfo shadowImageInfo{};
        if (m_shadowMap) {
            shadowImageInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
            shadowImageInfo.imageView = m_shadowMap->getImageView();
            shadowImageInfo.sampler = m_shadowMap->getSampler();

            VkWriteDescriptorSet shadowWrite{};
            shadowWrite.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            shadowWrite.dstSet = m_descriptorSets[i];
            shadowWrite.dstBinding = 1;
            shadowWrite.dstArrayElement = 0;
            shadowWrite.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
            shadowWrite.descriptorCount = 1;
            shadowWrite.pImageInfo = &shadowImageInfo;
            descriptorWrites.push_back(shadowWrite);
        }

        vkUpdateDescriptorSets(m_context.getDevice(), static_cast<u32>(descriptorWrites.size()),
                               descriptorWrites.data(), 0, nullptr);
    }
}

void Renderer::createPipeline() {
    m_pipelineLayout = PipelineLayoutBuilder(m_context)
        .addDescriptorSetLayout(m_descriptorSetLayout)
        .addPushConstantRange(VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(PushConstants))
        .build();

    VkSampleCountFlagBits msaaSamples = m_context.getMsaaSamples();

    PipelineConfig config = PipelineConfig::defaultConfig();
    config.renderPass = m_renderPass;
    config.pipelineLayout = m_pipelineLayout;
    config.multisample.rasterizationSamples = msaaSamples;
    // Enable sample shading for better quality (reduces aliasing inside polygons)
    if (msaaSamples != VK_SAMPLE_COUNT_1_BIT) {
        config.multisample.sampleShadingEnable = VK_TRUE;
        config.multisample.minSampleShading = 0.2f;  // Min fraction of samples to shade
    }

    m_pipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                             "shaders/structural.frag.spv", config);

    // Wireframe pipeline
    PipelineConfig wireframeConfig = PipelineConfig::defaultConfig();
    wireframeConfig.renderPass = m_renderPass;
    wireframeConfig.pipelineLayout = m_pipelineLayout;
    wireframeConfig.multisample.rasterizationSamples = msaaSamples;
    if (msaaSamples != VK_SAMPLE_COUNT_1_BIT) {
        wireframeConfig.multisample.sampleShadingEnable = VK_TRUE;
        wireframeConfig.multisample.minSampleShading = 0.2f;
    }
    wireframeConfig.rasterization.polygonMode = VK_POLYGON_MODE_LINE;
    wireframeConfig.rasterization.lineWidth = 1.5f;
    wireframeConfig.rasterization.cullMode = VK_CULL_MODE_NONE;

    m_wireframePipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                      "shaders/structural.frag.spv", wireframeConfig);

    // Create HDR pipelines (no MSAA, uses HDR render pass from PostProcess)
    if (m_postProcess) {
        PipelineConfig hdrConfig = PipelineConfig::defaultConfig();
        hdrConfig.renderPass = m_postProcess->getHDRRenderPass();
        hdrConfig.pipelineLayout = m_pipelineLayout;
        hdrConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;  // No MSAA for HDR

        m_hdrPipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                   "shaders/structural.frag.spv", hdrConfig);

        // HDR wireframe pipeline
        PipelineConfig hdrWireframeConfig = PipelineConfig::defaultConfig();
        hdrWireframeConfig.renderPass = m_postProcess->getHDRRenderPass();
        hdrWireframeConfig.pipelineLayout = m_pipelineLayout;
        hdrWireframeConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
        hdrWireframeConfig.rasterization.polygonMode = VK_POLYGON_MODE_LINE;
        hdrWireframeConfig.rasterization.lineWidth = 1.5f;
        hdrWireframeConfig.rasterization.cullMode = VK_CULL_MODE_NONE;

        m_hdrWireframePipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                            "shaders/structural.frag.spv", hdrWireframeConfig);
    }

    // Sky pipeline - renders fullscreen triangle behind everything
    createSkyPipeline();
}

void Renderer::createSkyPipeline() {
    // Create sky-specific descriptor set layout (UBO + environment cubemap)
    std::array<VkDescriptorSetLayoutBinding, 2> bindings{};

    // Binding 0: UBO (same as main pipeline)
    bindings[0].binding = 0;
    bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    bindings[0].descriptorCount = 1;
    bindings[0].stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 1: Environment cubemap
    bindings[1].binding = 1;
    bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[1].descriptorCount = 1;
    bindings[1].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    VkDescriptorSetLayoutCreateInfo layoutCreateInfo{};
    layoutCreateInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layoutCreateInfo.bindingCount = static_cast<u32>(bindings.size());
    layoutCreateInfo.pBindings = bindings.data();

    if (vkCreateDescriptorSetLayout(m_context.getDevice(), &layoutCreateInfo, nullptr, &m_skyDescriptorSetLayout) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create sky descriptor set layout");
    }

    // Allocate sky descriptor sets
    u32 imageCount = m_context.getSwapchainImageCount();
    m_skyDescriptorSets.resize(imageCount);
    std::vector<VkDescriptorSetLayout> layouts(imageCount, m_skyDescriptorSetLayout);

    VkDescriptorSetAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    allocInfo.descriptorPool = m_descriptorPool;
    allocInfo.descriptorSetCount = imageCount;
    allocInfo.pSetLayouts = layouts.data();

    if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, m_skyDescriptorSets.data()) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate sky descriptor sets");
    }

    // Update sky descriptor sets
    for (size_t i = 0; i < imageCount; ++i) {
        VkDescriptorBufferInfo bufferInfo{};
        bufferInfo.buffer = m_uniformBuffers[i];
        bufferInfo.offset = 0;
        bufferInfo.range = sizeof(UniformBufferObject);

        VkDescriptorImageInfo envMapInfo = m_envMap->getDescriptorInfo();

        std::array<VkWriteDescriptorSet, 2> writes{};

        writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[0].dstSet = m_skyDescriptorSets[i];
        writes[0].dstBinding = 0;
        writes[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        writes[0].descriptorCount = 1;
        writes[0].pBufferInfo = &bufferInfo;

        writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[1].dstSet = m_skyDescriptorSets[i];
        writes[1].dstBinding = 1;
        writes[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        writes[1].descriptorCount = 1;
        writes[1].pImageInfo = &envMapInfo;

        vkUpdateDescriptorSets(m_context.getDevice(), static_cast<u32>(writes.size()), writes.data(), 0, nullptr);
    }

    // Sky push constants: sun direction (xyz) + useHdr flag (w)
    VkPushConstantRange pushRange{};
    pushRange.stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT;
    pushRange.offset = 0;
    pushRange.size = sizeof(vec4);

    VkPipelineLayoutCreateInfo pipelineLayoutInfo{};
    pipelineLayoutInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    pipelineLayoutInfo.setLayoutCount = 1;
    pipelineLayoutInfo.pSetLayouts = &m_skyDescriptorSetLayout;
    pipelineLayoutInfo.pushConstantRangeCount = 1;
    pipelineLayoutInfo.pPushConstantRanges = &pushRange;

    if (vkCreatePipelineLayout(m_context.getDevice(), &pipelineLayoutInfo, nullptr, &m_skyPipelineLayout) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create sky pipeline layout");
    }

    // Load shaders
    auto readFile = [](const std::string& filepath) -> std::vector<char> {
        std::ifstream file(filepath, std::ios::ate | std::ios::binary);
        if (!file.is_open()) throw std::runtime_error("Failed to open: " + filepath);
        size_t fileSize = static_cast<size_t>(file.tellg());
        std::vector<char> buffer(fileSize);
        file.seekg(0);
        file.read(buffer.data(), fileSize);
        return buffer;
    };

    auto vertCode = readFile("shaders/sky.vert.spv");
    auto fragCode = readFile("shaders/sky.frag.spv");

    VkShaderModuleCreateInfo moduleInfo{};
    moduleInfo.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;

    moduleInfo.codeSize = vertCode.size();
    moduleInfo.pCode = reinterpret_cast<const u32*>(vertCode.data());
    VkShaderModule vertModule;
    vkCreateShaderModule(m_context.getDevice(), &moduleInfo, nullptr, &vertModule);

    moduleInfo.codeSize = fragCode.size();
    moduleInfo.pCode = reinterpret_cast<const u32*>(fragCode.data());
    VkShaderModule fragModule;
    vkCreateShaderModule(m_context.getDevice(), &moduleInfo, nullptr, &fragModule);

    VkPipelineShaderStageCreateInfo stages[2] = {};
    stages[0].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module = vertModule;
    stages[0].pName = "main";
    stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module = fragModule;
    stages[1].pName = "main";

    // No vertex input for fullscreen triangle
    VkPipelineVertexInputStateCreateInfo vertexInput{};
    vertexInput.sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO;

    VkPipelineInputAssemblyStateCreateInfo inputAssembly{};
    inputAssembly.sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO;
    inputAssembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;

    VkPipelineViewportStateCreateInfo viewportState{};
    viewportState.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO;
    viewportState.viewportCount = 1;
    viewportState.scissorCount = 1;

    VkPipelineRasterizationStateCreateInfo rasterizer{};
    rasterizer.sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
    rasterizer.polygonMode = VK_POLYGON_MODE_FILL;
    rasterizer.cullMode = VK_CULL_MODE_NONE;
    rasterizer.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    rasterizer.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisampling{};
    multisampling.sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO;
    multisampling.rasterizationSamples = m_context.getMsaaSamples();

    VkPipelineDepthStencilStateCreateInfo depthStencil{};
    depthStencil.sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO;
    depthStencil.depthTestEnable = VK_FALSE;  // Sky renders behind everything
    depthStencil.depthWriteEnable = VK_FALSE;

    VkPipelineColorBlendAttachmentState colorBlendAttachment{};
    colorBlendAttachment.colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT |
                                          VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT;

    VkPipelineColorBlendStateCreateInfo colorBlending{};
    colorBlending.sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO;
    colorBlending.attachmentCount = 1;
    colorBlending.pAttachments = &colorBlendAttachment;

    VkDynamicState dynamicStates[] = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR};
    VkPipelineDynamicStateCreateInfo dynamicState{};
    dynamicState.sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO;
    dynamicState.dynamicStateCount = 2;
    dynamicState.pDynamicStates = dynamicStates;

    VkGraphicsPipelineCreateInfo pipelineInfo{};
    pipelineInfo.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO;
    pipelineInfo.stageCount = 2;
    pipelineInfo.pStages = stages;
    pipelineInfo.pVertexInputState = &vertexInput;
    pipelineInfo.pInputAssemblyState = &inputAssembly;
    pipelineInfo.pViewportState = &viewportState;
    pipelineInfo.pRasterizationState = &rasterizer;
    pipelineInfo.pMultisampleState = &multisampling;
    pipelineInfo.pDepthStencilState = &depthStencil;
    pipelineInfo.pColorBlendState = &colorBlending;
    pipelineInfo.pDynamicState = &dynamicState;
    pipelineInfo.layout = m_skyPipelineLayout;
    pipelineInfo.renderPass = m_renderPass;

    if (vkCreateGraphicsPipelines(m_context.getDevice(), m_context.getPipelineCache(), 1,
                                   &pipelineInfo, nullptr, &m_skyPipeline) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create sky pipeline");
    }

    vkDestroyShaderModule(m_context.getDevice(), vertModule, nullptr);
    vkDestroyShaderModule(m_context.getDevice(), fragModule, nullptr);
}

void Renderer::drawSky() {
    if (m_skyPipeline == VK_NULL_HANDLE) return;
    if (m_skyDescriptorSets.empty()) return;

    vkCmdBindPipeline(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, m_skyPipeline);

    // Bind sky descriptor set (includes UBO and environment cubemap)
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_skyPipelineLayout, 0, 1, &m_skyDescriptorSets[m_currentFrame], 0, nullptr);

    // Set viewport and scissor
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

    // Pass sun direction (xyz) and useHdr flag (w) to shader
    vec4 sunDir = vec4(m_lightDirection, m_useHdrEnvMap ? 1.0f : 0.0f);
    vkCmdPushConstants(m_currentCommandBuffer, m_skyPipelineLayout,
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(vec4), &sunDir);

    // Draw fullscreen triangle (3 vertices, no vertex buffer)
    vkCmdDraw(m_currentCommandBuffer, 3, 1, 0, 0);

    // Rebind the structural pipeline and descriptor sets for subsequent draws
    if (m_vizMode == VisualizationMode::Wireframe && m_wireframePipeline) {
        m_wireframePipeline->bind(m_currentCommandBuffer);
    } else if (m_pipeline) {
        m_pipeline->bind(m_currentCommandBuffer);
    }
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, 1, &m_descriptorSets[m_currentFrame], 0, nullptr);
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
    // Reset frame counter and per-image fence tracking
    m_currentFrame = 0;
    m_imagesInFlight.assign(m_context.getSwapchainImageCount(), VK_NULL_HANDLE);
}

void Renderer::onResize() {
    recreateSwapchain();
}

bool Renderer::beginFrame() {
    // Wait for the current frame-in-flight's fence
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

    // Check if a previous frame is still using this swapchain image
    if (m_imagesInFlight[m_imageIndex] != VK_NULL_HANDLE) {
        vkWaitForFences(m_context.getDevice(), 1, &m_imagesInFlight[m_imageIndex], VK_TRUE, UINT64_MAX);
    }
    // Mark this image as now being used by the current frame's fence
    m_imagesInFlight[m_imageIndex] = m_inFlightFences[m_currentFrame];

    vkResetFences(m_context.getDevice(), 1, &m_inFlightFences[m_currentFrame]);

    // Use m_currentFrame for command buffer (need enough for swapchain images)
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

    // Use per-image semaphore for render finished (indexed by acquired image)
    VkSemaphore signalSemaphores[] = {m_renderFinishedSemaphores[m_imageIndex]};
    submitInfo.signalSemaphoreCount = 1;
    submitInfo.pSignalSemaphores = signalSemaphores;

    if (vkQueueSubmit(m_context.getGraphicsQueue(), 1, &submitInfo, m_inFlightFences[m_currentFrame]) != VK_SUCCESS) {
        throw std::runtime_error("Failed to submit draw command buffer");
    }

    VkPresentInfoKHR presentInfo{};
    presentInfo.sType = VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
    presentInfo.waitSemaphoreCount = 1;
    presentInfo.pWaitSemaphores = signalSemaphores;  // Same semaphore indexed by m_imageIndex

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

    // Cycle through frames in flight (typically 2)
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

    VkSampleCountFlagBits msaaSamples = m_context.getMsaaSamples();
    bool useMsaa = msaaSamples != VK_SAMPLE_COUNT_1_BIT;

    std::vector<VkClearValue> clearValues;
    if (useMsaa) {
        // MSAA: 3 attachments - MSAA color, resolve (no clear needed), MSAA depth
        VkClearValue colorClear{};
        colorClear.color = {{clearColor.r, clearColor.g, clearColor.b, clearColor.a}};
        clearValues.push_back(colorClear);  // MSAA color

        VkClearValue resolveClear{};  // Not actually used since loadOp is DONT_CARE
        clearValues.push_back(resolveClear);  // Resolve target

        VkClearValue depthClear{};
        depthClear.depthStencil = {1.0f, 0};
        clearValues.push_back(depthClear);  // MSAA depth
    } else {
        VkClearValue colorClear{};
        colorClear.color = {{clearColor.r, clearColor.g, clearColor.b, clearColor.a}};
        clearValues.push_back(colorClear);

        VkClearValue depthClear{};
        depthClear.depthStencil = {1.0f, 0};
        clearValues.push_back(depthClear);
    }

    renderPassInfo.clearValueCount = static_cast<u32>(clearValues.size());
    renderPassInfo.pClearValues = clearValues.data();

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
    if (m_vizMode == VisualizationMode::Wireframe && m_wireframePipeline) {
        m_wireframePipeline->bind(m_currentCommandBuffer);
    } else if (m_pipeline) {
        m_pipeline->bind(m_currentCommandBuffer);
    }
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, 1, &m_descriptorSets[m_currentFrame], 0, nullptr);
}

void Renderer::endRenderPass() {
    vkCmdEndRenderPass(m_currentCommandBuffer);
}

void Renderer::beginHDRRenderPass(vec4 clearColor) {
    if (!m_postProcess || !m_hdrPipeline) return;

    VkRenderPassBeginInfo renderPassInfo{};
    renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    renderPassInfo.renderPass = m_postProcess->getHDRRenderPass();
    renderPassInfo.framebuffer = m_postProcess->getHDRFramebuffer();
    renderPassInfo.renderArea.offset = {0, 0};
    renderPassInfo.renderArea.extent = m_context.getSwapchainExtent();

    std::array<VkClearValue, 2> clearValues{};
    clearValues[0].color = {{clearColor.r, clearColor.g, clearColor.b, clearColor.a}};
    clearValues[1].depthStencil = {1.0f, 0};

    renderPassInfo.clearValueCount = static_cast<u32>(clearValues.size());
    renderPassInfo.pClearValues = clearValues.data();

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

    // Bind HDR-compatible pipeline based on visualization mode
    if (m_vizMode == VisualizationMode::Wireframe && m_hdrWireframePipeline) {
        m_hdrWireframePipeline->bind(m_currentCommandBuffer);
    } else if (m_hdrPipeline) {
        m_hdrPipeline->bind(m_currentCommandBuffer);
    }
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, 1, &m_descriptorSets[m_currentFrame], 0, nullptr);
}

void Renderer::endHDRRenderPass() {
    vkCmdEndRenderPass(m_currentCommandBuffer);
}

void Renderer::runPostProcessing() {
    if (!m_postProcess) return;

    auto extent = m_context.getSwapchainExtent();
    f32 aspectRatio = static_cast<f32>(extent.width) / static_cast<f32>(extent.height);

    // Compute view and projection matrices for SSAO
    mat4 view = m_camera.getViewMatrix();
    mat4 proj = m_camera.getProjectionMatrix(aspectRatio);
    proj[1][1] *= -1;  // Flip Y for Vulkan

    // Generate SSAO from HDR depth buffer
    if (m_ssaoEnabled) {
        m_postProcess->generateSSAO(
            m_currentCommandBuffer,
            m_postProcess->getHDRDepthView(),
            nullptr,  // No separate normal buffer yet
            proj,
            view
        );
    }

    // Generate bloom from HDR color buffer
    if (m_bloomEnabled) {
        m_postProcess->generateBloom(m_currentCommandBuffer);
    }
}

void Renderer::beginCompositePass() {
    if (!m_postProcess) return;

    auto extent = m_context.getSwapchainExtent();

    // Run composite pass - begins swapchain render pass but doesn't end it (for ImGui)
    m_postProcess->composite(
        m_currentCommandBuffer,
        m_renderPass,
        m_framebuffers[m_imageIndex],
        extent,
        true,   // Begin render pass
        false   // Don't end render pass (ImGui will render, then endRenderPass)
    );
}

void Renderer::renderShadowPass(const std::vector<StructuralElement>& elements) {
    if (!m_shadowMap || !m_shadowsEnabled || elements.empty()) {
        return;
    }

    // Calculate scene bounds for light matrix
    vec3 minBounds(FLT_MAX);
    vec3 maxBounds(-FLT_MAX);
    for (const auto& elem : elements) {
        minBounds = glm::min(minBounds, glm::min(elem.start, elem.end));
        maxBounds = glm::max(maxBounds, glm::max(elem.start, elem.end));
    }
    vec3 sceneCenter = (minBounds + maxBounds) * 0.5f;
    f32 sceneRadius = glm::length(maxBounds - minBounds) * 0.5f;
    sceneRadius = glm::max(sceneRadius, 10.0f);  // Minimum radius

    // Update light matrices
    m_shadowMap->updateLightMatrix(m_lightDirection, sceneCenter, sceneRadius);

    // Begin shadow pass
    m_shadowMap->beginShadowPass(m_currentCommandBuffer);

    // Shadow push constants structure
    struct ShadowPushConstants {
        mat4 lightViewProj;
        mat4 model;
    };

    // Draw all elements to shadow map - mirror drawStructuralFrame logic
    for (const auto& elem : elements) {
        std::string key;
        mat4 transform = mat4(1.0f);

        switch (elem.type) {
            case ElementType::Beam: {
                f32 length = glm::length(elem.end - elem.start);
                key = "beam_" + std::to_string(length) + "_" +
                      std::to_string(elem.width) + "_" + std::to_string(elem.depth);

                vec3 dir = glm::normalize(elem.end - elem.start);
                vec3 up = vec3(0, 1, 0);
                if (std::abs(glm::dot(dir, up)) > 0.99f) up = vec3(0, 0, 1);

                transform = glm::translate(mat4(1.0f), elem.start);
                vec3 right = glm::normalize(glm::cross(up, dir));
                vec3 localUp = glm::cross(dir, right);
                mat4 rotation(1.0f);
                rotation[0] = vec4(dir, 0);
                rotation[1] = vec4(localUp, 0);
                rotation[2] = vec4(right, 0);
                transform = transform * rotation;
                break;
            }
            case ElementType::Column: {
                f32 height = elem.end.y - elem.start.y;
                key = "col_" + std::to_string(elem.width) + "_" + std::to_string(elem.depth) + "_" + std::to_string(height);
                transform = glm::translate(mat4(1.0f), elem.start);
                break;
            }
            case ElementType::Wall: {
                // Check for custom mesh (gable walls use custom geometry)
                if (elem.mesh.hasData()) {
                    auto cacheIt = m_customMeshKeyCache.find(&elem.mesh);
                    if (cacheIt != m_customMeshKeyCache.end()) {
                        key = cacheIt->second;
                    } else {
                        continue;  // Mesh not yet cached by main pass
                    }
                    transform = mat4(1.0f);  // Custom meshes are in world space
                } else {
                    f32 height = elem.end.y - elem.start.y;
                    f32 xExtent = elem.end.x - elem.start.x;
                    f32 zExtent = elem.end.z - elem.start.z;
                    // Use std::abs() to match key generation in drawColumnWithMaterial
                    key = "col_" + std::to_string(std::abs(xExtent)) + "_" + std::to_string(std::abs(zExtent)) + "_" + std::to_string(height);
                    vec3 center = (elem.start + elem.end) * 0.5f;
                    center.y = elem.start.y;
                    transform = glm::translate(mat4(1.0f), center);
                }
                break;
            }
            case ElementType::Floor: {
                if (elem.mesh.hasData()) {
                    auto cacheIt = m_customMeshKeyCache.find(&elem.mesh);
                    if (cacheIt != m_customMeshKeyCache.end()) {
                        key = cacheIt->second;
                    } else {
                        continue;
                    }
                    transform = mat4(1.0f);
                } else {
                    f32 floorWidth = elem.end.x - elem.start.x;
                    f32 floorDepth = elem.end.z - elem.start.z;
                    key = "floor_" + std::to_string(floorWidth) + "_" + std::to_string(floorDepth) + "_" + std::to_string(elem.depth);
                    vec3 center = (elem.start + elem.end) * 0.5f;
                    center.y = elem.start.y;
                    transform = glm::translate(mat4(1.0f), center);
                }
                break;
            }
            case ElementType::Door: {
                if (elem.mesh.hasData()) {
                    auto cacheIt = m_customMeshKeyCache.find(&elem.mesh);
                    if (cacheIt != m_customMeshKeyCache.end()) {
                        key = cacheIt->second;
                    } else {
                        continue;
                    }
                    transform = mat4(1.0f);
                } else {
                    f32 xExtent = elem.end.x - elem.start.x;
                    f32 zExtent = elem.end.z - elem.start.z;
                    f32 doorHeight = elem.end.y - elem.start.y;
                    f32 doorWidth = std::max(std::abs(xExtent), std::abs(zExtent));
                    f32 doorDepth = std::min(std::abs(xExtent), std::abs(zExtent));
                    if (doorDepth < 0.1f) doorDepth = elem.depth;
                    key = "door_" + std::to_string(doorWidth) + "_" + std::to_string(doorHeight) + "_" + std::to_string(doorDepth);
                    vec3 center = (elem.start + elem.end) * 0.5f;
                    center.y = elem.start.y;
                    f32 rotation = 0.0f;
                    if (std::abs(zExtent) > std::abs(xExtent)) {
                        rotation = glm::radians(90.0f);
                    }
                    transform = glm::translate(mat4(1.0f), center);
                    transform = glm::rotate(transform, rotation, vec3(0.0f, 1.0f, 0.0f));
                }
                break;
            }
            case ElementType::Window:
                // Skip windows in shadow pass - light passes through glass
                continue;
            case ElementType::Roof: {
                // Check for custom mesh (QBD roofs use custom geometry)
                if (elem.mesh.hasData()) {
                    auto cacheIt = m_customMeshKeyCache.find(&elem.mesh);
                    if (cacheIt != m_customMeshKeyCache.end()) {
                        key = cacheIt->second;
                    } else {
                        continue;
                    }
                    transform = mat4(1.0f);
                } else {
                    // Fallback roof key
                    f32 roofWidth = std::abs(elem.end.x - elem.start.x);
                    f32 roofDepthZ = std::abs(elem.end.z - elem.start.z);
                    f32 roofThickness = elem.end.y - elem.start.y;
                    if (roofThickness < 0.1f) roofThickness = 0.5f;
                    key = "roof_" + std::to_string(roofWidth) + "_" + std::to_string(roofDepthZ) + "_" + std::to_string(roofThickness);
                    vec3 center = (elem.start + elem.end) * 0.5f;
                    center.y = elem.start.y;
                    transform = glm::translate(mat4(1.0f), center);
                }
                break;
            }
            default:
                continue;  // Skip other types
        }

        auto it = m_meshCache.find(key);
        if (it == m_meshCache.end()) {
            continue;  // Skip if mesh not cached
        }

        ShadowPushConstants shadowPush;
        shadowPush.lightViewProj = m_shadowMap->getLightViewProj();
        shadowPush.model = transform;

        vkCmdPushConstants(m_currentCommandBuffer, m_shadowMap->getPipelineLayout(),
                           VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(ShadowPushConstants), &shadowPush);

        it->second->bind(m_currentCommandBuffer);
        it->second->draw(m_currentCommandBuffer);
    }

    m_shadowMap->endShadowPass(m_currentCommandBuffer);
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

    // Shadow mapping data
    if (m_shadowMap && m_shadowsEnabled) {
        ubo.lightViewProj = m_shadowMap->getLightViewProj();
        ubo.lightDirection = vec4(m_lightDirection, 0.0f);
        ubo.shadowBias = 0.008f;  // Increased bias to reduce shadow acne
        ubo.enableShadows = 1;
    } else {
        ubo.lightViewProj = mat4(1.0f);
        ubo.lightDirection = vec4(0.0f, -1.0f, 0.0f, 0.0f);
        ubo.shadowBias = 0.0f;
        ubo.enableShadows = 0;
    }

    // Section clipping data
    ubo.clipPlane = m_clipPlane;
    ubo.enableClipping = m_clippingEnabled ? 1 : 0;

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

void Renderer::applyMaterialStyle() {
    switch (m_materialStyle) {
        case MaterialStyle::Realistic: {
            // Full PBR materials with realistic properties
            auto wall = Materials::Drywall();
            m_wallMetallic = wall.metallic;
            m_wallRoughness = wall.roughness;
            m_wallAO = wall.ao;
            m_wallEmission = wall.emission;

            auto roof = Materials::Asphalt();
            m_roofMetallic = roof.metallic;
            m_roofRoughness = roof.roughness;
            m_roofAO = roof.ao;
            m_roofEmission = roof.emission;

            m_defaultMetallic = 0.0f;
            m_defaultRoughness = 0.5f;
            m_defaultAO = 1.0f;
            m_defaultEmission = 0.0f;
            break;
        }
        case MaterialStyle::Clean: {
            // Clean matte surfaces
            m_wallMetallic = 0.0f;
            m_wallRoughness = 0.9f;
            m_wallAO = 1.0f;
            m_wallEmission = 0.0f;

            m_roofMetallic = 0.0f;
            m_roofRoughness = 0.85f;
            m_roofAO = 1.0f;
            m_roofEmission = 0.0f;

            m_defaultMetallic = 0.0f;
            m_defaultRoughness = 0.7f;
            m_defaultAO = 1.0f;
            m_defaultEmission = 0.0f;
            break;
        }
        case MaterialStyle::Schematic: {
            // Flat colors, no PBR effects
            m_wallMetallic = 0.0f;
            m_wallRoughness = 1.0f;
            m_wallAO = 1.0f;
            m_wallEmission = 0.0f;

            m_roofMetallic = 0.0f;
            m_roofRoughness = 1.0f;
            m_roofAO = 1.0f;
            m_roofEmission = 0.0f;

            m_defaultMetallic = 0.0f;
            m_defaultRoughness = 1.0f;
            m_defaultAO = 1.0f;
            m_defaultEmission = 0.0f;
            break;
        }
        case MaterialStyle::Blueprint: {
            // Blueprint style - all surfaces flat
            m_wallMetallic = 0.0f;
            m_wallRoughness = 1.0f;
            m_wallAO = 1.0f;
            m_wallEmission = 0.1f;  // Slight emission for blueprint glow

            m_roofMetallic = 0.0f;
            m_roofRoughness = 1.0f;
            m_roofAO = 1.0f;
            m_roofEmission = 0.1f;

            m_defaultMetallic = 0.0f;
            m_defaultRoughness = 1.0f;
            m_defaultAO = 1.0f;
            m_defaultEmission = 0.1f;
            break;
        }
    }
}

MaterialPreset Renderer::getMaterialForElement(ElementType type) const {
    switch (m_materialStyle) {
        case MaterialStyle::Realistic:
            switch (type) {
                case ElementType::Beam:    return Materials::Steel();
                case ElementType::Column:  return Materials::Concrete();
                case ElementType::Floor:   return Materials::Hardwood();
                case ElementType::Wall:    return Materials::Drywall();
                case ElementType::Foundation: return Materials::Concrete();
                case ElementType::Connection: return Materials::Steel();
                case ElementType::Door:    return Materials::OakWood();
                case ElementType::Window:  return Materials::Glass();
                case ElementType::Roof:    return Materials::Asphalt();
                default: return Materials::Concrete();
            }

        case MaterialStyle::Clean:
            // Clean style: same colors but more matte
            switch (type) {
                case ElementType::Beam:    return {{0.6f, 0.65f, 0.7f}, 0.0f, 0.7f, 1.0f, 0.0f};
                case ElementType::Column:  return {{0.6f, 0.6f, 0.6f}, 0.0f, 0.8f, 1.0f, 0.0f};
                case ElementType::Floor:   return {{0.5f, 0.4f, 0.3f}, 0.0f, 0.7f, 1.0f, 0.0f};
                case ElementType::Wall:    return {{0.9f, 0.88f, 0.85f}, 0.0f, 0.9f, 1.0f, 0.0f};
                case ElementType::Foundation: return {{0.5f, 0.5f, 0.5f}, 0.0f, 0.85f, 1.0f, 0.0f};
                case ElementType::Connection: return {{0.5f, 0.5f, 0.55f}, 0.0f, 0.6f, 1.0f, 0.0f};
                case ElementType::Door:    return {{0.55f, 0.35f, 0.2f}, 0.0f, 0.75f, 1.0f, 0.0f};
                case ElementType::Window:  return {{0.7f, 0.85f, 0.95f}, 0.0f, 0.3f, 1.0f, 0.0f};
                case ElementType::Roof:    return {{0.35f, 0.35f, 0.38f}, 0.0f, 0.85f, 1.0f, 0.0f};
                default: return {{0.6f, 0.6f, 0.6f}, 0.0f, 0.8f, 1.0f, 0.0f};
            }

        case MaterialStyle::Schematic:
            // Schematic: flat colors for technical drawings
            switch (type) {
                case ElementType::Beam:    return {{0.3f, 0.3f, 0.8f}, 0.0f, 1.0f, 1.0f, 0.0f};  // Blue
                case ElementType::Column:  return {{0.8f, 0.3f, 0.3f}, 0.0f, 1.0f, 1.0f, 0.0f};  // Red
                case ElementType::Floor:   return {{0.7f, 0.7f, 0.7f}, 0.0f, 1.0f, 1.0f, 0.0f};  // Gray
                case ElementType::Wall:    return {{0.95f, 0.95f, 0.9f}, 0.0f, 1.0f, 1.0f, 0.0f}; // Off-white
                case ElementType::Foundation: return {{0.5f, 0.5f, 0.5f}, 0.0f, 1.0f, 1.0f, 0.0f}; // Dark gray
                case ElementType::Connection: return {{0.8f, 0.8f, 0.3f}, 0.0f, 1.0f, 1.0f, 0.0f}; // Yellow
                case ElementType::Door:    return {{0.6f, 0.4f, 0.2f}, 0.0f, 1.0f, 1.0f, 0.0f};  // Brown
                case ElementType::Window:  return {{0.6f, 0.8f, 1.0f}, 0.0f, 1.0f, 1.0f, 0.0f};  // Light blue
                case ElementType::Roof:    return {{0.4f, 0.4f, 0.45f}, 0.0f, 1.0f, 1.0f, 0.0f}; // Dark gray
                default: return {{0.6f, 0.6f, 0.6f}, 0.0f, 1.0f, 1.0f, 0.0f};
            }

        case MaterialStyle::Blueprint:
            // Blueprint: blue/white technical style
            switch (type) {
                case ElementType::Beam:    return {{0.2f, 0.4f, 0.8f}, 0.0f, 1.0f, 1.0f, 0.15f};
                case ElementType::Column:  return {{0.2f, 0.5f, 0.9f}, 0.0f, 1.0f, 1.0f, 0.15f};
                case ElementType::Floor:   return {{0.15f, 0.35f, 0.7f}, 0.0f, 1.0f, 1.0f, 0.1f};
                case ElementType::Wall:    return {{0.25f, 0.45f, 0.85f}, 0.0f, 1.0f, 1.0f, 0.12f};
                case ElementType::Foundation: return {{0.1f, 0.3f, 0.6f}, 0.0f, 1.0f, 1.0f, 0.1f};
                case ElementType::Connection: return {{0.95f, 0.95f, 1.0f}, 0.0f, 1.0f, 1.0f, 0.2f}; // White
                case ElementType::Door:    return {{0.3f, 0.5f, 0.8f}, 0.0f, 1.0f, 1.0f, 0.12f};
                case ElementType::Window:  return {{0.4f, 0.6f, 0.95f}, 0.0f, 1.0f, 1.0f, 0.15f};
                case ElementType::Roof:    return {{0.18f, 0.38f, 0.75f}, 0.0f, 1.0f, 1.0f, 0.1f};
                default: return {{0.2f, 0.45f, 0.85f}, 0.0f, 1.0f, 1.0f, 0.12f};
            }

        default:
            return Materials::Concrete();
    }
}

void Renderer::drawMesh(Mesh& mesh, const mat4& transform, vec3 color, f32 stress) {
    // Use default material
    drawMeshWithMaterial(mesh, transform, color, stress,
                         vec4(m_defaultMetallic, m_defaultRoughness, m_defaultAO, m_defaultEmission));
}

void Renderer::drawMeshWithMaterial(Mesh& mesh, const mat4& transform, vec3 color, f32 stress, vec4 material) {
    PushConstants push{};
    push.model = transform;
    push.color = vec4(color, stress);  // stress in alpha controls shader behavior
    push.material = material;

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

void Renderer::drawColumnWithMaterial(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress, vec4 material) {
    std::string key = "col_" + std::to_string(width) + "_" + std::to_string(depth) + "_" + std::to_string(height);

    if (m_meshCache.find(key) == m_meshCache.end()) {
        auto [verts, indices] = Geometry::createColumn(vec3(0), width, depth, height, color);
        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
    }

    mat4 transform = glm::translate(mat4(1.0f), position);
    drawMeshWithMaterial(*m_meshCache[key], transform, color, stress, material);
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

    // Check cache first to avoid recalculating hash
    const MeshData* meshPtr = &meshData;
    std::string key;
    auto cacheIt = m_customMeshKeyCache.find(meshPtr);
    if (cacheIt != m_customMeshKeyCache.end()) {
        key = cacheIt->second;
    } else {
        // Create unique key based on mesh data hash
        size_t hash = 0;
        for (const auto& v : meshData.vertices) {
            hash ^= std::hash<float>{}(v.x) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
            hash ^= std::hash<float>{}(v.y) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
            hash ^= std::hash<float>{}(v.z) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
        }
        key = "custom_" + std::to_string(hash);
        m_customMeshKeyCache[meshPtr] = key;
    }

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

void Renderer::drawCustomMeshWithMaterial(const MeshData& meshData, vec3 color, f32 stress, vec4 material) {
    if (!meshData.hasData()) return;

    // Check cache first to avoid recalculating hash
    const MeshData* meshPtr = &meshData;
    std::string key;
    auto cacheIt = m_customMeshKeyCache.find(meshPtr);
    if (cacheIt != m_customMeshKeyCache.end()) {
        key = cacheIt->second;
    } else {
        // Create unique key based on mesh data hash
        size_t hash = 0;
        for (const auto& v : meshData.vertices) {
            hash ^= std::hash<float>{}(v.x) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
            hash ^= std::hash<float>{}(v.y) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
            hash ^= std::hash<float>{}(v.z) + 0x9e3779b9 + (hash << 6) + (hash >> 2);
        }
        key = "custom_" + std::to_string(hash);
        m_customMeshKeyCache[meshPtr] = key;
    }

    if (m_meshCache.find(key) == m_meshCache.end()) {
        std::vector<Vertex> vertices;
        std::vector<u32> indices;

        for (const auto& face : meshData.faces) {
            const vec3& v0 = meshData.vertices[face[0]];
            const vec3& v1 = meshData.vertices[face[1]];
            const vec3& v2 = meshData.vertices[face[2]];

            vec3 edge1 = v1 - v0;
            vec3 edge2 = v2 - v0;
            vec3 normal = glm::normalize(glm::cross(edge1, edge2));

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

    mat4 transform = mat4(1.0f);
    drawMeshWithMaterial(*m_meshCache[key], transform, color, stress, material);
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
                             element.end.y - element.start.y, color, stressForShader);  // Use vertical extent as thickness
                }
                break;
            }

            case ElementType::Wall: {
                // Use custom mesh if available (e.g., gable wall)
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Generate wall geometry - supports diagonal walls
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float height = element.end.y - element.start.y;

                    // Check if this is a diagonal wall (both X and Z extents significant)
                    bool isDiagonal = std::abs(xExtent) > 0.1f && std::abs(zExtent) > 0.1f;

                    // Wall material
                    vec4 wallMat = vec4(m_wallMetallic, m_wallRoughness, m_wallAO, m_wallEmission);

                    if (isDiagonal) {
                        // Diagonal wall - use beam geometry
                        // Beam is centered on start-end line, so offset to wall mid-height
                        float midHeight = element.start.y + height * 0.5f;
                        vec3 wallStart = vec3(element.start.x, midHeight, element.start.z);
                        vec3 wallEnd = vec3(element.end.x, midHeight, element.end.z);

                        // Calculate wall thickness (use depth or a default)
                        float thickness = element.depth > 0.01f ? element.depth : 0.5f;

                        // Create unique key for diagonal wall
                        std::string key = "diagwall_" + std::to_string(xExtent) + "_" +
                                         std::to_string(zExtent) + "_" + std::to_string(height) + "_" +
                                         std::to_string(thickness);

                        if (m_meshCache.find(key) == m_meshCache.end()) {
                            // Create beam geometry: width=thickness (perpendicular), height=wall height (vertical)
                            auto [verts, indices] = Geometry::createBeam(
                                wallStart, wallEnd, thickness, height, vec3(1.0f));
                            m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                        }

                        // Draw with wall material
                        drawMeshWithMaterial(*m_meshCache[key], mat4(1.0f), color, stressForShader, wallMat);
                    } else {
                        // Axis-aligned wall - use column geometry with wall material
                        glm::vec3 center = (element.start + element.end) * 0.5f;
                        center.y = element.start.y;

                        // Use element.depth for wall thickness, not the extent (which would be 0 for axis-aligned walls)
                        float wallThickness = element.depth > 0.01f ? element.depth : 0.5f;

                        if (std::abs(xExtent) > std::abs(zExtent)) {
                            // Wall runs along X axis: width=length, depth=thickness
                            drawColumnWithMaterial(center, std::abs(xExtent), wallThickness, height, color, stressForShader, wallMat);
                        } else {
                            // Wall runs along Z axis: width=thickness, depth=length
                            drawColumnWithMaterial(center, wallThickness, std::abs(zExtent), height, color, stressForShader, wallMat);
                        }
                    }
                }
                break;
            }

            case ElementType::Door: {
                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry using beam-based approach
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float doorHeight = element.end.y - element.start.y;
                    float doorDepth = element.depth > 0.1f ? element.depth : 100.0f;

                    // Door start/end are along the wall direction at floor level
                    // Create door as a beam from start to end, with height as vertical extent
                    vec3 doorStart = vec3(element.start.x, element.start.y + doorHeight * 0.5f, element.start.z);
                    vec3 doorEnd = vec3(element.end.x, element.start.y + doorHeight * 0.5f, element.end.z);

                    // Use diagonal length for width (supports diagonal walls)
                    float doorWidth = glm::length(vec2(xExtent, zExtent));
                    std::string key = "doordirect_" + std::to_string(doorWidth) + "_" +
                                     std::to_string(doorHeight) + "_" + std::to_string(doorDepth) +
                                     "_" + std::to_string(xExtent) + "_" + std::to_string(zExtent);

                    if (m_meshCache.find(key) == m_meshCache.end()) {
                        // Use beam geometry: doorDepth=thickness (perpendicular), doorHeight=height (vertical)
                        auto [verts, indices] = Geometry::createBeam(
                            doorStart, doorEnd, doorDepth, doorHeight, color);
                        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                    }

                    drawMesh(*m_meshCache[key], mat4(1.0f), color, stressForShader);
                }
                break;
            }

            case ElementType::Window: {
                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMesh(element.mesh, color, stressForShader);
                } else {
                    // Fall back to generated geometry using beam-based approach
                    float xExtent = element.end.x - element.start.x;
                    float zExtent = element.end.z - element.start.z;
                    float windowHeight = element.end.y - element.start.y;
                    float windowDepth = element.depth > 0.1f ? element.depth : 100.0f;

                    // Window start/end are along the wall direction at sill height
                    // Create window as a beam from start to end, with height as vertical extent
                    vec3 windowStart = vec3(element.start.x, element.start.y + windowHeight * 0.5f, element.start.z);
                    vec3 windowEnd = vec3(element.end.x, element.start.y + windowHeight * 0.5f, element.end.z);

                    // Use diagonal length for width (supports diagonal walls)
                    float windowWidth = glm::length(vec2(xExtent, zExtent));
                    std::string key = "windowdirect_" + std::to_string(windowWidth) + "_" +
                                     std::to_string(windowHeight) + "_" + std::to_string(windowDepth) +
                                     "_" + std::to_string(xExtent) + "_" + std::to_string(zExtent);

                    if (m_meshCache.find(key) == m_meshCache.end()) {
                        // Use beam geometry: windowDepth=thickness (perpendicular), windowHeight=height (vertical)
                        auto [verts, indices] = Geometry::createBeam(
                            windowStart, windowEnd, windowDepth, windowHeight, vec3(0.7f, 0.85f, 0.95f));
                        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                    }

                    drawMesh(*m_meshCache[key], mat4(1.0f), color, stressForShader);
                }
                break;
            }

            case ElementType::Roof: {
                // Roof material
                vec4 roofMat = vec4(m_roofMetallic, m_roofRoughness, m_roofAO, m_roofEmission);

                // Use actual IFC mesh if available
                if (element.mesh.hasData()) {
                    drawCustomMeshWithMaterial(element.mesh, color, stressForShader, roofMat);
                } else {
                    // Fall back to generated geometry
                    float roofWidth = std::abs(element.end.x - element.start.x);
                    float roofDepthZ = std::abs(element.end.z - element.start.z);
                    float roofThickness = element.end.y - element.start.y;
                    if (roofThickness < 0.1f) roofThickness = 0.5f;

                    glm::vec3 center = (element.start + element.end) * 0.5f;
                    center.y = element.start.y;

                    // Use roof material for generated roof geometry
                    std::string key = "roof_" + std::to_string(roofWidth) + "_" + std::to_string(roofDepthZ) + "_" + std::to_string(roofThickness);
                    if (m_meshCache.find(key) == m_meshCache.end()) {
                        auto [verts, indices] = Geometry::createFloorSlab(vec3(0), roofWidth, roofDepthZ, roofThickness);
                        m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                    }
                    mat4 transform = glm::translate(mat4(1.0f), center);
                    drawMeshWithMaterial(*m_meshCache[key], transform, color, stressForShader, roofMat);
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

void Renderer::updateClipPlane() {
    // Create clip plane based on axis and height
    // Clip plane equation: ax + by + cz + d = 0
    // Points with dot(pos, plane) > 0 are kept
    vec3 normal(0.0f);
    switch (m_clipAxis) {
        case 0: normal.x = m_clipFlipped ? -1.0f : 1.0f; break;  // X axis
        case 1: normal.y = m_clipFlipped ? -1.0f : 1.0f; break;  // Y axis
        case 2: normal.z = m_clipFlipped ? -1.0f : 1.0f; break;  // Z axis
    }
    // d = -dot(normal, point_on_plane)
    // point_on_plane is (height, 0, 0) for X axis, etc.
    f32 d = -m_clipHeight * (m_clipFlipped ? -1.0f : 1.0f);
    m_clipPlane = vec4(normal, d);
}

bool Renderer::loadHdrEnvironment(const std::string& filepath) {
    if (!m_envMap) {
        m_envMap = std::make_unique<EnvironmentMap>(m_context);
    }

    bool success = m_envMap->loadFromFile(filepath);
    if (success) {
        m_useHdrEnvMap = true;
    }
    return success;
}

// SSAO settings
void Renderer::setSSAOEnabled(bool enabled) {
    m_ssaoEnabled = enabled;
    if (m_postProcess) {
        auto config = m_postProcess->getSSAOConfig();
        config.enabled = enabled;
        m_postProcess->setSSAOConfig(config);
    }
}

void Renderer::setSSAORadius(f32 radius) {
    if (m_postProcess) {
        auto config = m_postProcess->getSSAOConfig();
        config.radius = radius;
        m_postProcess->setSSAOConfig(config);
    }
}

f32 Renderer::getSSAORadius() const {
    return m_postProcess ? m_postProcess->getSSAOConfig().radius : 0.5f;
}

void Renderer::setSSAOIntensity(f32 intensity) {
    if (m_postProcess) {
        auto config = m_postProcess->getSSAOConfig();
        config.intensity = intensity;
        m_postProcess->setSSAOConfig(config);
    }
}

f32 Renderer::getSSAOIntensity() const {
    return m_postProcess ? m_postProcess->getSSAOConfig().intensity : 1.5f;
}

void Renderer::setSSAOBias(f32 bias) {
    if (m_postProcess) {
        auto config = m_postProcess->getSSAOConfig();
        config.bias = bias;
        m_postProcess->setSSAOConfig(config);
    }
}

f32 Renderer::getSSAOBias() const {
    return m_postProcess ? m_postProcess->getSSAOConfig().bias : 0.025f;
}

// Bloom settings
void Renderer::setBloomEnabled(bool enabled) {
    m_bloomEnabled = enabled;
    if (m_postProcess) {
        auto config = m_postProcess->getBloomConfig();
        config.enabled = enabled;
        m_postProcess->setBloomConfig(config);
    }
}

void Renderer::setBloomThreshold(f32 threshold) {
    if (m_postProcess) {
        auto config = m_postProcess->getBloomConfig();
        config.threshold = threshold;
        m_postProcess->setBloomConfig(config);
    }
}

f32 Renderer::getBloomThreshold() const {
    return m_postProcess ? m_postProcess->getBloomConfig().threshold : 1.0f;
}

void Renderer::setBloomIntensity(f32 intensity) {
    if (m_postProcess) {
        auto config = m_postProcess->getBloomConfig();
        config.intensity = intensity;
        m_postProcess->setBloomConfig(config);
    }
}

f32 Renderer::getBloomIntensity() const {
    return m_postProcess ? m_postProcess->getBloomConfig().intensity : 0.3f;
}

void Renderer::setBloomIterations(u32 iterations) {
    if (m_postProcess) {
        auto config = m_postProcess->getBloomConfig();
        config.iterations = iterations;
        m_postProcess->setBloomConfig(config);
    }
}

u32 Renderer::getBloomIterations() const {
    return m_postProcess ? m_postProcess->getBloomConfig().iterations : 5;
}

// Tonemapping settings
void Renderer::setExposure(f32 exposure) {
    if (m_postProcess) {
        auto config = m_postProcess->getCompositeConfig();
        config.exposure = exposure;
        m_postProcess->setCompositeConfig(config);
    }
}

f32 Renderer::getExposure() const {
    return m_postProcess ? m_postProcess->getCompositeConfig().exposure : 1.0f;
}

void Renderer::setTonemapMode(u32 mode) {
    if (m_postProcess) {
        auto config = m_postProcess->getCompositeConfig();
        config.tonemapMode = mode;
        m_postProcess->setCompositeConfig(config);
    }
}

u32 Renderer::getTonemapMode() const {
    return m_postProcess ? m_postProcess->getCompositeConfig().tonemapMode : 1;
}

#if 0  // Ray tracing disabled - incomplete implementation (missing header declarations)
// Ray tracing implementation
void Renderer::initRayTracing() {
    if (m_rayTracingInitialized) return;
    if (!m_context.isRayTracingSupported()) return;

    m_accelStructManager = std::make_unique<AccelerationStructureManager>(m_context);
    m_rtPipeline = std::make_unique<RayTracingPipeline>(m_context);

    if (!m_rtPipeline->initialize()) {
        m_accelStructManager.reset();
        m_rtPipeline.reset();
        return;
    }

    m_rayTracingInitialized = true;
}

bool Renderer::isRayTracingAvailable() const {
    return m_context.isRayTracingSupported();
}

void Renderer::setRayTracingEnabled(bool enabled) {
    if (enabled && !m_rayTracingInitialized) {
        initRayTracing();
    }
    m_rayTracingEnabled = enabled && m_rayTracingInitialized;
}

void Renderer::resetRayTracingAccumulation() {
    m_rtSamples = 0;
    if (m_rtPipeline) {
        m_rtPipeline->resetAccumulation();
    }
}

void Renderer::createRTSceneBuffers() {
    if (m_rtVertices.empty()) return;

    VkDevice device = m_context.getDevice();

    // Cleanup old buffers
    m_rtVertexBuffer.destroy(device);
    m_rtIndexBuffer.destroy(device);
    m_rtMaterialBuffer.destroy(device);

    // Create vertex buffer
    VkDeviceSize vertexSize = m_rtVertices.size() * sizeof(Vertex);
    VkBufferCreateInfo bufferInfo{};
    bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bufferInfo.size = vertexSize;
    bufferInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT |
                       VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT_KHR;
    bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    vkCreateBuffer(device, &bufferInfo, nullptr, &m_rtVertexBuffer.buffer);

    VkMemoryRequirements memReqs;
    vkGetBufferMemoryRequirements(device, m_rtVertexBuffer.buffer, &memReqs);

    VkMemoryAllocateFlagsInfo flagsInfo{};
    flagsInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO;
    flagsInfo.flags = VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT;

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.pNext = &flagsInfo;
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(
        memReqs.memoryTypeBits,
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);

    vkAllocateMemory(device, &allocInfo, nullptr, &m_rtVertexBuffer.memory);
    vkBindBufferMemory(device, m_rtVertexBuffer.buffer, m_rtVertexBuffer.memory, 0);
    m_rtVertexBuffer.size = vertexSize;

    // Copy vertex data
    void* data;
    vkMapMemory(device, m_rtVertexBuffer.memory, 0, vertexSize, 0, &data);
    memcpy(data, m_rtVertices.data(), vertexSize);
    vkUnmapMemory(device, m_rtVertexBuffer.memory);

    // Create index buffer
    VkDeviceSize indexSize = m_rtIndices.size() * sizeof(u32);
    bufferInfo.size = indexSize;
    bufferInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT |
                       VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT_KHR;

    vkCreateBuffer(device, &bufferInfo, nullptr, &m_rtIndexBuffer.buffer);
    vkGetBufferMemoryRequirements(device, m_rtIndexBuffer.buffer, &memReqs);

    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(
        memReqs.memoryTypeBits,
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);

    vkAllocateMemory(device, &allocInfo, nullptr, &m_rtIndexBuffer.memory);
    vkBindBufferMemory(device, m_rtIndexBuffer.buffer, m_rtIndexBuffer.memory, 0);
    m_rtIndexBuffer.size = indexSize;

    // Copy index data
    vkMapMemory(device, m_rtIndexBuffer.memory, 0, indexSize, 0, &data);
    memcpy(data, m_rtIndices.data(), indexSize);
    vkUnmapMemory(device, m_rtIndexBuffer.memory);

    // Create material buffer
    if (!m_rtMaterials.empty()) {
        VkDeviceSize materialSize = m_rtMaterials.size() * sizeof(RTMaterial);
        bufferInfo.size = materialSize;
        bufferInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;

        vkCreateBuffer(device, &bufferInfo, nullptr, &m_rtMaterialBuffer.buffer);
        vkGetBufferMemoryRequirements(device, m_rtMaterialBuffer.buffer, &memReqs);

        // Material buffer doesn't need device address, just storage
        VkMemoryAllocateInfo matAllocInfo{};
        matAllocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        matAllocInfo.allocationSize = memReqs.size;
        matAllocInfo.memoryTypeIndex = m_context.findMemoryType(
            memReqs.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);

        vkAllocateMemory(device, &matAllocInfo, nullptr, &m_rtMaterialBuffer.memory);
        vkBindBufferMemory(device, m_rtMaterialBuffer.buffer, m_rtMaterialBuffer.memory, 0);
        m_rtMaterialBuffer.size = materialSize;

        // Copy material data
        vkMapMemory(device, m_rtMaterialBuffer.memory, 0, materialSize, 0, &data);
        memcpy(data, m_rtMaterials.data(), materialSize);
        vkUnmapMemory(device, m_rtMaterialBuffer.memory);
    }
}

void Renderer::buildAccelerationStructures(const std::vector<StructuralElement>& elements) {
    if (!m_rayTracingInitialized) {
        initRayTracing();
        if (!m_rayTracingInitialized) return;
    }

    m_rtVertices.clear();
    m_rtIndices.clear();
    m_rtMaterials.clear();
    std::vector<BLASInstance> instances;

    // Destroy old acceleration structures
    m_accelStructManager->cleanup();

    // Create BLAS for each element using createBeam as the base geometry
    for (const auto& elem : elements) {
        // Get physically-based material for this element type
        RTMaterial material = ArchMaterials::forElementType(elem.type);

        // Get color from material albedo for vertex color (used as fallback)
        vec3 color = vec3(material.albedoAndMetallic);

        std::vector<Vertex> vertices;
        std::vector<u32> indices;

        // Use createBeam for most elements as a simple box representation
        auto result = Geometry::createBeam(elem.start, elem.end, elem.width, elem.depth, color);
        vertices = result.first;
        indices = result.second;

        if (vertices.empty()) continue;

        // Store offset for global index buffer
        u32 vertexOffset = static_cast<u32>(m_rtVertices.size());

        // Add vertices to global buffer
        m_rtVertices.insert(m_rtVertices.end(), vertices.begin(), vertices.end());

        // Add indices with offset
        for (u32 idx : indices) {
            m_rtIndices.push_back(idx + vertexOffset);
        }

        // Store material for this instance
        m_rtMaterials.push_back(material);

        // Create BLAS for this geometry
        u32 blasIndex = m_accelStructManager->createBLAS(vertices, indices);

        // Create instance (identity transform since beam already has position)
        BLASInstance instance;
        instance.blasIndex = blasIndex;
        instance.transform = mat4(1.0f);
        instance.customIndex = static_cast<u32>(instances.size());  // Material index
        instances.push_back(instance);
    }

    if (instances.empty()) return;

    // Build TLAS from all instances
    m_accelStructManager->buildTLAS(instances);

    // Create scene buffers for shader access
    createRTSceneBuffers();

    // Update descriptors in ray tracing pipeline
    if (m_rtPipeline && m_accelStructManager->getTLASHandle() != VK_NULL_HANDLE) {
        m_rtPipeline->updateDescriptors(
            m_accelStructManager->getTLASHandle(),
            m_rtPipeline->getOutputImageView(),
            m_rtVertexBuffer.buffer,
            m_rtIndexBuffer.buffer,
            m_rtMaterialBuffer.buffer
        );
    }

    // Reset accumulation since scene changed
    resetRayTracingAccumulation();
}

void Renderer::renderRayTraced() {
    if (!m_rayTracingEnabled || !m_rtPipeline || !m_accelStructManager) return;
    if (m_accelStructManager->getTLASHandle() == VK_NULL_HANDLE) return;

    auto extent = m_context.getSwapchainExtent();
    f32 aspectRatio = static_cast<f32>(extent.width) / static_cast<f32>(extent.height);

    // Get camera matrices
    mat4 view = m_camera.getViewMatrix();
    mat4 proj = m_camera.getProjectionMatrix(aspectRatio);
    mat4 viewProj = proj * view;

    // Update denoising settings
    m_rtPipeline->setDenoisingEnabled(m_rtDenoisingEnabled);
    m_rtPipeline->setDenoiseStrength(m_rtDenoiseStrength);
    m_rtPipeline->setPrevViewProj(m_prevViewProj);

    // Update camera UBO
    RTCameraUBO rtCamera;
    rtCamera.viewInverse = glm::inverse(view);
    rtCamera.projInverse = glm::inverse(proj);
    rtCamera.prevViewProj = m_prevViewProj;
    rtCamera.lightDir = vec4(m_lightDirection, 0.0f);
    rtCamera.cameraPos = vec4(m_camera.position, 1.0f);
    rtCamera.frameCount = m_rtSamples;
    rtCamera.sampleCount = 1024;
    rtCamera.time = m_time;
    rtCamera.exposure = getExposure();
    rtCamera.enableDenoising = m_rtDenoisingEnabled ? 1 : 0;
    rtCamera.denoiseStrength = m_rtDenoiseStrength;

    m_rtPipeline->updateCamera(rtCamera);

    // Record ray tracing commands
    m_rtPipeline->recordCommands(m_currentCommandBuffer, extent.width, extent.height);

    // Store current view-projection for next frame
    m_prevViewProj = viewProj;

    m_rtSamples++;
}

void Renderer::setRTDenoisingEnabled(bool enabled) {
    m_rtDenoisingEnabled = enabled;
    if (m_rtPipeline) {
        m_rtPipeline->setDenoisingEnabled(enabled);
    }
}

void Renderer::setRTDenoiseStrength(f32 strength) {
    m_rtDenoiseStrength = glm::clamp(strength, 0.0f, 1.0f);
    if (m_rtPipeline) {
        m_rtPipeline->setDenoiseStrength(m_rtDenoiseStrength);
    }
}
#endif  // Ray tracing disabled

} // namespace arch
