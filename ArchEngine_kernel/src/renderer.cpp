#include "renderer.hpp"
#include <stdexcept>
#include <cstring>
#include <array>
#include <iostream>
#include <algorithm>
#include <cctype>
#include <filesystem>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

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
    m_postProcess->createCompositePipeline(m_renderPass, m_context.getMsaaSamples());

    createDescriptorPool();
    createUniformBuffers();
    createDescriptorSets();
    createMaterialDescriptorSetLayout();
    createDefaultMaterialDescriptorSet();

    // Create shadow height map descriptor set for tessellated shadows
    if (m_shadowMap && m_shadowMap->getHeightMapDescriptorSetLayout() != VK_NULL_HANDLE) {
        VkDescriptorSetAllocateInfo allocInfo{};
        allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        allocInfo.descriptorPool = m_descriptorPool;
        allocInfo.descriptorSetCount = 1;
        VkDescriptorSetLayout shadowHeightLayout = m_shadowMap->getHeightMapDescriptorSetLayout();
        allocInfo.pSetLayouts = &shadowHeightLayout;

        if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, &m_shadowHeightMapDescriptorSet) == VK_SUCCESS) {
            // Bind default black texture (no displacement)
            VkDescriptorImageInfo heightMapInfo{};
            heightMapInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
            heightMapInfo.imageView = Texture::getBlack()->getImageView();
            heightMapInfo.sampler = Texture::getBlack()->getSampler();

            VkWriteDescriptorSet write{};
            write.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            write.dstSet = m_shadowHeightMapDescriptorSet;
            write.dstBinding = 0;
            write.dstArrayElement = 0;
            write.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
            write.descriptorCount = 1;
            write.pImageInfo = &heightMapInfo;

            vkUpdateDescriptorSets(m_context.getDevice(), 1, &write, 0, nullptr);
        }
    }

    createPipeline();

    // Create grid mesh
    auto [gridVerts, gridIndices] = Geometry::createGrid(100.0f, 5.0f);
    m_gridMesh = std::make_unique<Mesh>(m_context, gridVerts, gridIndices);
}

Renderer::~Renderer() {
    m_context.waitIdle();

    // Cleanup high-resolution resources (for high-res rendering/screenshots)
    cleanupHighResResources();

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
    m_transparentPipeline.reset();
    m_hdrPipeline.reset();
    m_hdrWireframePipeline.reset();
    m_hdrTransparentPipeline.reset();
    m_tessPipeline.reset();
    m_tessWireframePipeline.reset();
    m_hdrTessPipeline.reset();
    m_hdrTessWireframePipeline.reset();

    for (size_t i = 0; i < m_context.getSwapchainImageCount(); ++i) {
        vkDestroyBuffer(m_context.getDevice(), m_uniformBuffers[i], nullptr);
        vkFreeMemory(m_context.getDevice(), m_uniformBuffersMemory[i], nullptr);
    }

    // Cleanup material resources
    m_materialLibrary.reset();
    if (m_materialDescriptorSetLayout != VK_NULL_HANDLE) {
        vkDestroyDescriptorSetLayout(m_context.getDevice(), m_materialDescriptorSetLayout, nullptr);
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

    // Sampler pool size (shadow map + environment cubemap + material textures + shadow height map)
    // Material set needs 8 samplers: albedo, normal, roughness, metallic, ao, emissive, opacity, height
    VkDescriptorPoolSize samplerPoolSize{};
    samplerPoolSize.type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    samplerPoolSize.descriptorCount = imageCount * 2 + (8 * kMaxMaterialSets) + 1;  // +1 for shadow height map
    poolSizes.push_back(samplerPoolSize);

    VkDescriptorPoolCreateInfo poolInfo{};
    poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    poolInfo.poolSizeCount = static_cast<u32>(poolSizes.size());
    poolInfo.pPoolSizes = poolSizes.data();
    poolInfo.maxSets = imageCount * 2 + 1 + kMaxMaterialSets + 1;  // main + sky + material + shadow height map
    poolInfo.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;  // Allow individual set freeing

    if (vkCreateDescriptorPool(m_context.getDevice(), &poolInfo, nullptr, &m_descriptorPool) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create descriptor pool");
    }

    std::vector<VkDescriptorSetLayoutBinding> bindings;

    // Binding 0: UBO
    VkDescriptorSetLayoutBinding uboBinding{};
    uboBinding.binding = 0;
    uboBinding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    uboBinding.descriptorCount = 1;
    uboBinding.stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT;
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

void Renderer::createMaterialDescriptorSetLayout() {
    // Material descriptor set layout (set 1) - 8 texture samplers
    std::array<VkDescriptorSetLayoutBinding, 8> bindings{};

    // Binding 0: Albedo texture
    bindings[0].binding = 0;
    bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[0].descriptorCount = 1;
    bindings[0].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 1: Normal map
    bindings[1].binding = 1;
    bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[1].descriptorCount = 1;
    bindings[1].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 2: Roughness map
    bindings[2].binding = 2;
    bindings[2].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[2].descriptorCount = 1;
    bindings[2].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 3: Metallic map
    bindings[3].binding = 3;
    bindings[3].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[3].descriptorCount = 1;
    bindings[3].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 4: AO map
    bindings[4].binding = 4;
    bindings[4].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[4].descriptorCount = 1;
    bindings[4].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 5: Emissive map
    bindings[5].binding = 5;
    bindings[5].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[5].descriptorCount = 1;
    bindings[5].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 6: Opacity map
    bindings[6].binding = 6;
    bindings[6].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[6].descriptorCount = 1;
    bindings[6].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    // Binding 7: Height/displacement map (used by tessellation evaluation shader)
    bindings[7].binding = 7;
    bindings[7].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[7].descriptorCount = 1;
    bindings[7].stageFlags = VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT | VK_SHADER_STAGE_FRAGMENT_BIT;

    VkDescriptorSetLayoutCreateInfo layoutInfo{};
    layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layoutInfo.bindingCount = static_cast<u32>(bindings.size());
    layoutInfo.pBindings = bindings.data();

    if (vkCreateDescriptorSetLayout(m_context.getDevice(), &layoutInfo, nullptr, &m_materialDescriptorSetLayout) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create material descriptor set layout");
    }
}

void Renderer::createDefaultMaterialDescriptorSet() {
    // Create material library and default textures
    m_materialLibrary = std::make_unique<MaterialLibrary>(m_context);
    m_materialLibrary->createBuiltinMaterials();
    m_materialLibrary->loadMaterialsFromDirectory(m_materialRoot);

    // Allocate descriptor set for default material
    VkDescriptorSetAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    allocInfo.descriptorPool = m_descriptorPool;
    allocInfo.descriptorSetCount = 1;
    allocInfo.pSetLayouts = &m_materialDescriptorSetLayout;

    if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, &m_defaultMaterialDescriptorSet) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate default material descriptor set");
    }

    // Get default textures
    Texture* albedo = Texture::getWhite();
    Texture* normal = Texture::getNormalDefault();
    Texture* roughness = Texture::getWhite();
    Texture* metallic = Texture::getBlack();
    Texture* ao = Texture::getWhite();
    Texture* emissive = Texture::getBlack();
    Texture* opacity = Texture::getWhite();
    Texture* height = Texture::getBlack();  // No displacement by default

    // Write descriptor set
    std::array<VkDescriptorImageInfo, 8> imageInfos{};
    imageInfos[0] = {albedo->getSampler(), albedo->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[1] = {normal->getSampler(), normal->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[2] = {roughness->getSampler(), roughness->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[3] = {metallic->getSampler(), metallic->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[4] = {ao->getSampler(), ao->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[5] = {emissive->getSampler(), emissive->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[6] = {opacity->getSampler(), opacity->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[7] = {height->getSampler(), height->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};

    std::array<VkWriteDescriptorSet, 8> writes{};
    for (size_t i = 0; i < writes.size(); ++i) {
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet = m_defaultMaterialDescriptorSet;
        writes[i].dstBinding = static_cast<u32>(i);
        writes[i].dstArrayElement = 0;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        writes[i].descriptorCount = 1;
        writes[i].pImageInfo = &imageInfos[i];
    }

    vkUpdateDescriptorSets(m_context.getDevice(), static_cast<u32>(writes.size()), writes.data(), 0, nullptr);

    // Build descriptor sets for all loaded materials
    buildMaterialDescriptorSets();
}

bool Renderer::reloadMaterialLibrary(const std::string& root) {
    if (!m_materialLibrary) {
        return false;
    }

    // Wait for GPU to finish using current textures before reloading
    vkDeviceWaitIdle(m_context.getDevice());

    m_materialRoot = root.empty() ? "materials" : root;
    m_materialLibrary->loadMaterialsFromDirectory(m_materialRoot);
    buildMaterialDescriptorSets();
    return true;
}

std::vector<std::string> Renderer::getMaterialNames() const {
    std::vector<std::string> names;
    if (!m_materialLibrary) {
        return names;
    }

    names.reserve(m_materialLibrary->getMaterials().size());
    for (const auto& [name, mat] : m_materialLibrary->getMaterials()) {
        if (!mat) continue;
        names.push_back(name);
    }
    std::sort(names.begin(), names.end());
    return names;
}

void Renderer::createPipeline() {
    m_pipelineLayout = PipelineLayoutBuilder(m_context)
        .addDescriptorSetLayout(m_descriptorSetLayout)           // Set 0: UBO + shadow map
        .addDescriptorSetLayout(m_materialDescriptorSetLayout)   // Set 1: Material textures
        .addPushConstantRange(VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT, 0, sizeof(PushConstants))
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

    // Transparent pipeline for glass/windows (alpha blending enabled)
    PipelineConfig transparentConfig = PipelineConfig::transparentConfig();
    transparentConfig.renderPass = m_renderPass;
    transparentConfig.pipelineLayout = m_pipelineLayout;
    transparentConfig.multisample.rasterizationSamples = msaaSamples;
    if (msaaSamples != VK_SAMPLE_COUNT_1_BIT) {
        transparentConfig.multisample.sampleShadingEnable = VK_TRUE;
        transparentConfig.multisample.minSampleShading = 0.2f;
    }

    m_transparentPipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                        "shaders/structural.frag.spv", transparentConfig);

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

        // HDR transparent pipeline for glass/windows
        PipelineConfig hdrTransparentConfig = PipelineConfig::transparentConfig();
        hdrTransparentConfig.renderPass = m_postProcess->getHDRRenderPass();
        hdrTransparentConfig.pipelineLayout = m_pipelineLayout;
        hdrTransparentConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

        m_hdrTransparentPipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                               "shaders/structural.frag.spv", hdrTransparentConfig);
    }

    // Create tessellation pipelines for displacement mapping
    {
        PipelineConfig tessConfig = PipelineConfig::tessellationConfig();
        tessConfig.renderPass = m_renderPass;
        tessConfig.pipelineLayout = m_pipelineLayout;
        tessConfig.multisample.rasterizationSamples = msaaSamples;
        if (msaaSamples != VK_SAMPLE_COUNT_1_BIT) {
            tessConfig.multisample.sampleShadingEnable = VK_TRUE;
            tessConfig.multisample.minSampleShading = 0.2f;
        }

        m_tessPipeline = std::make_unique<Pipeline>(m_context,
            "shaders/structural.vert.spv",
            "shaders/structural.tesc.spv",
            "shaders/structural.tese.spv",
            "shaders/structural.frag.spv",
            tessConfig);

        // Tessellation wireframe
        PipelineConfig tessWireConfig = PipelineConfig::tessellationConfig();
        tessWireConfig.renderPass = m_renderPass;
        tessWireConfig.pipelineLayout = m_pipelineLayout;
        tessWireConfig.multisample.rasterizationSamples = msaaSamples;
        if (msaaSamples != VK_SAMPLE_COUNT_1_BIT) {
            tessWireConfig.multisample.sampleShadingEnable = VK_TRUE;
            tessWireConfig.multisample.minSampleShading = 0.2f;
        }
        tessWireConfig.rasterization.polygonMode = VK_POLYGON_MODE_LINE;
        tessWireConfig.rasterization.lineWidth = 1.5f;
        tessWireConfig.rasterization.cullMode = VK_CULL_MODE_NONE;

        m_tessWireframePipeline = std::make_unique<Pipeline>(m_context,
            "shaders/structural.vert.spv",
            "shaders/structural.tesc.spv",
            "shaders/structural.tese.spv",
            "shaders/structural.frag.spv",
            tessWireConfig);

        // HDR tessellation pipelines
        if (m_postProcess) {
            PipelineConfig hdrTessConfig = PipelineConfig::tessellationConfig();
            hdrTessConfig.renderPass = m_postProcess->getHDRRenderPass();
            hdrTessConfig.pipelineLayout = m_pipelineLayout;
            hdrTessConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

            m_hdrTessPipeline = std::make_unique<Pipeline>(m_context,
                "shaders/structural.vert.spv",
                "shaders/structural.tesc.spv",
                "shaders/structural.tese.spv",
                "shaders/structural.frag.spv",
                hdrTessConfig);

            PipelineConfig hdrTessWireConfig = PipelineConfig::tessellationConfig();
            hdrTessWireConfig.renderPass = m_postProcess->getHDRRenderPass();
            hdrTessWireConfig.pipelineLayout = m_pipelineLayout;
            hdrTessWireConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
            hdrTessWireConfig.rasterization.polygonMode = VK_POLYGON_MODE_LINE;
            hdrTessWireConfig.rasterization.lineWidth = 1.5f;
            hdrTessWireConfig.rasterization.cullMode = VK_CULL_MODE_NONE;

            m_hdrTessWireframePipeline = std::make_unique<Pipeline>(m_context,
                "shaders/structural.vert.spv",
                "shaders/structural.tesc.spv",
                "shaders/structural.tese.spv",
                "shaders/structural.frag.spv",
                hdrTessWireConfig);
        }
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
    bindings[0].stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT;

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
    pushRange.stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT;
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
    // Sky pipeline is built for the swapchain render pass only.
    // Skip it when rendering to HDR to avoid render pass mismatch.
    if (m_outputLinearHDR) return;
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
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT, 0, sizeof(vec4), &sunDir);

    // Draw fullscreen triangle (3 vertices, no vertex buffer)
    vkCmdDraw(m_currentCommandBuffer, 3, 1, 0, 0);

    // Rebind the structural pipeline and descriptor sets for subsequent draws
    if (m_vizMode == VisualizationMode::Wireframe) {
        if (m_tessellationEnabled && m_tessWireframePipeline) {
            m_tessWireframePipeline->bind(m_currentCommandBuffer);
        } else if (m_wireframePipeline) {
            m_wireframePipeline->bind(m_currentCommandBuffer);
        }
    } else {
        if (m_tessellationEnabled && m_tessPipeline) {
            m_tessPipeline->bind(m_currentCommandBuffer);
        } else if (m_pipeline) {
            m_pipeline->bind(m_currentCommandBuffer);
        }
    }

    // Rebind both descriptor sets
    std::array<VkDescriptorSet, 2> descriptorSets = {
        m_descriptorSets[m_currentFrame],
        m_defaultMaterialDescriptorSet
    };
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, static_cast<u32>(descriptorSets.size()),
                            descriptorSets.data(), 0, nullptr);
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
    if (m_postProcess) {
        auto extent = m_context.getSwapchainExtent();
        m_postProcess->resize(extent.width, extent.height);
        m_postProcess->createCompositePipeline(m_renderPass, m_context.getMsaaSamples());
    }
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
    m_lastBoundMaterialSet = VK_NULL_HANDLE;  // Reset for new frame

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
    // Direct rendering - apply tonemapping in shader
    m_outputLinearHDR = false;
    updateUniformBuffer(m_currentFrame);

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

    // Bind appropriate pipeline based on visualization mode and tessellation
    if (m_vizMode == VisualizationMode::Wireframe) {
        if (m_tessellationEnabled && m_tessWireframePipeline) {
            m_tessWireframePipeline->bind(m_currentCommandBuffer);
        } else if (m_wireframePipeline) {
            m_wireframePipeline->bind(m_currentCommandBuffer);
        }
    } else {
        if (m_tessellationEnabled && m_tessPipeline) {
            m_tessPipeline->bind(m_currentCommandBuffer);
        } else if (m_pipeline) {
            m_pipeline->bind(m_currentCommandBuffer);
        }
    }

    // Bind both descriptor sets: set 0 (UBO + shadow) and set 1 (material textures)
    std::array<VkDescriptorSet, 2> descriptorSets = {
        m_descriptorSets[m_currentFrame],
        m_defaultMaterialDescriptorSet
    };
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, static_cast<u32>(descriptorSets.size()),
                            descriptorSets.data(), 0, nullptr);
}

void Renderer::endRenderPass() {
    vkCmdEndRenderPass(m_currentCommandBuffer);
}

void Renderer::beginHDRRenderPass(vec4 clearColor) {
    if (!m_postProcess || !m_hdrPipeline) return;

    // Enable linear HDR output (composite pass will do tonemapping)
    m_outputLinearHDR = true;
    updateUniformBuffer(m_currentFrame);

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

    // Bind HDR-compatible pipeline based on visualization mode and tessellation
    if (m_vizMode == VisualizationMode::Wireframe) {
        if (m_tessellationEnabled && m_hdrTessWireframePipeline) {
            m_hdrTessWireframePipeline->bind(m_currentCommandBuffer);
        } else if (m_hdrWireframePipeline) {
            m_hdrWireframePipeline->bind(m_currentCommandBuffer);
        }
    } else {
        if (m_tessellationEnabled && m_hdrTessPipeline) {
            m_hdrTessPipeline->bind(m_currentCommandBuffer);
        } else if (m_hdrPipeline) {
            m_hdrPipeline->bind(m_currentCommandBuffer);
        }
    }

    // Bind both descriptor sets: set 0 (UBO + shadow) and set 1 (material textures)
    std::array<VkDescriptorSet, 2> descriptorSets = {
        m_descriptorSets[m_currentFrame],
        m_defaultMaterialDescriptorSet
    };
    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 0, static_cast<u32>(descriptorSets.size()),
                            descriptorSets.data(), 0, nullptr);
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
            view,
            m_currentFrame
        );
    }

    // Generate bloom from HDR color buffer
    if (m_bloomEnabled) {
        m_postProcess->generateBloom(m_currentCommandBuffer, m_currentFrame);
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
        m_currentFrame,
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

    // Begin shadow pass - beginShadowPass binds the non-tessellated pipeline by default
    m_shadowMap->beginShadowPass(m_currentCommandBuffer);

    // Check if we should use tessellated shadow pipeline
    bool useTessShadows = m_tessellationEnabled && m_shadowMap->getTessPipeline() != VK_NULL_HANDLE
                          && m_shadowHeightMapDescriptorSet != VK_NULL_HANDLE;

    if (useTessShadows) {
        // Bind tessellated shadow pipeline
        vkCmdBindPipeline(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, m_shadowMap->getTessPipeline());

        // Bind height map descriptor set
        vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                                m_shadowMap->getTessPipelineLayout(), 0, 1,
                                &m_shadowHeightMapDescriptorSet, 0, nullptr);
    }

    // Shadow push constants structure (non-tessellated)
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
                    f32 doorDepth = elem.depth > 0.1f ? elem.depth : 0.5f;

                    // Calculate actual door width from wall direction vector
                    f32 doorWidth = glm::length(vec2(xExtent, zExtent));
                    if (doorWidth < 0.01f || doorHeight < 0.01f) continue;

                    // Use consistent key with main rendering pass
                    key = "door_proper_" + std::to_string(static_cast<int>(doorWidth * 100)) + "_" +
                          std::to_string(static_cast<int>(doorHeight * 100)) + "_" +
                          std::to_string(static_cast<int>(doorDepth * 100));

                    vec3 center = (elem.start + elem.end) * 0.5f;
                    center.y = elem.start.y;

                    // Calculate rotation from extents (negate for proper alignment)
                    f32 rotation = -std::atan2(zExtent, xExtent);

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

        if (useTessShadows) {
            // Use tessellated push constants
            ShadowTessPushConstants tessPush;
            tessPush.lightViewProj = m_shadowMap->getLightViewProj();
            tessPush.model = transform;
            tessPush.tessLevel = m_tessellationLevel;
            tessPush.dispScale = m_displacementScale;
            tessPush.uvScale = m_materialUVScale;
            tessPush.padding = 0.0f;

            vkCmdPushConstants(m_currentCommandBuffer, m_shadowMap->getTessPipelineLayout(),
                               VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT,
                               0, sizeof(ShadowTessPushConstants), &tessPush);
        } else {
            // Use non-tessellated push constants
            ShadowPushConstants shadowPush;
            shadowPush.lightViewProj = m_shadowMap->getLightViewProj();
            shadowPush.model = transform;

            vkCmdPushConstants(m_currentCommandBuffer, m_shadowMap->getPipelineLayout(),
                               VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(ShadowPushConstants), &shadowPush);
        }

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
        ubo.shadowBias = m_shadowBias;  // Use adjustable shadow bias
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

    // HDR output mode (skip tonemapping in shader when rendering to HDR buffer)
    ubo.outputLinearHDR = m_outputLinearHDR ? 1 : 0;
    ubo.exposure = getExposure();

    // Tessellation parameters for displacement mapping
    ubo.tessellationLevel = m_tessellationEnabled ? m_tessellationLevel : 1.0f;
    ubo.displacementScale = m_tessellationEnabled ? m_displacementScale : 0.0f;

    // Material params: uvScale, normalStrength, brightness, contrast
    ubo.materialParams = vec4(m_materialUVScale, m_normalStrength, m_materialBrightness, m_materialContrast);
    // Material params2: saturation, roughnessOffset, metallicOffset, aoStrength
    ubo.materialParams2 = vec4(m_materialSaturation, m_materialRoughnessOffset, m_materialMetallicOffset, m_materialAOStrength);
    // Material tint
    ubo.materialTint = vec4(m_materialTint, 1.0f);

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
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT,
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
        auto calcWorldUV = [](vec3 pos, vec3 normal, f32 uvScale = 0.001f) -> vec2 {
            vec3 uAxis, vAxis;
            if (std::abs(normal.y) > 0.9f) {
                uAxis = vec3(1, 0, 0);
                vAxis = vec3(0, 0, 1);
            } else if (std::abs(normal.x) > std::abs(normal.z)) {
                uAxis = vec3(0, 0, 1);
                vAxis = vec3(0, 1, 0);
            } else {
                uAxis = vec3(1, 0, 0);
                vAxis = vec3(0, 1, 0);
            }
            return vec2(glm::dot(pos, uAxis) * uvScale, glm::dot(pos, vAxis) * uvScale);
        };

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
            vertices.push_back({v0, normal, color, calcWorldUV(v0, normal)});
            vertices.push_back({v1, normal, color, calcWorldUV(v1, normal)});
            vertices.push_back({v2, normal, color, calcWorldUV(v2, normal)});

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
        auto calcWorldUV = [](vec3 pos, vec3 normal, f32 uvScale = 0.001f) -> vec2 {
            vec3 uAxis, vAxis;
            if (std::abs(normal.y) > 0.9f) {
                uAxis = vec3(1, 0, 0);
                vAxis = vec3(0, 0, 1);
            } else if (std::abs(normal.x) > std::abs(normal.z)) {
                uAxis = vec3(0, 0, 1);
                vAxis = vec3(0, 1, 0);
            } else {
                uAxis = vec3(1, 0, 0);
                vAxis = vec3(0, 1, 0);
            }
            return vec2(glm::dot(pos, uAxis) * uvScale, glm::dot(pos, vAxis) * uvScale);
        };

        for (const auto& face : meshData.faces) {
            const vec3& v0 = meshData.vertices[face[0]];
            const vec3& v1 = meshData.vertices[face[1]];
            const vec3& v2 = meshData.vertices[face[2]];

            vec3 edge1 = v1 - v0;
            vec3 edge2 = v2 - v0;
            vec3 normal = glm::normalize(glm::cross(edge1, edge2));

            u32 baseIndex = static_cast<u32>(vertices.size());
            vertices.push_back({v0, normal, color, calcWorldUV(v0, normal)});
            vertices.push_back({v1, normal, color, calcWorldUV(v1, normal)});
            vertices.push_back({v2, normal, color, calcWorldUV(v2, normal)});

            indices.push_back(baseIndex + 0);
            indices.push_back(baseIndex + 1);
            indices.push_back(baseIndex + 2);
        }

        m_meshCache[key] = std::make_unique<Mesh>(m_context, vertices, indices);
    }

    mat4 transform = mat4(1.0f);
    drawMeshWithMaterial(*m_meshCache[key], transform, color, stress, material);
}

VkDescriptorSet Renderer::createMaterialDescriptorSetForMaterial(const Material& material) {
    VkDescriptorSet descSet = VK_NULL_HANDLE;

    VkDescriptorSetAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    allocInfo.descriptorPool = m_descriptorPool;
    allocInfo.descriptorSetCount = 1;
    allocInfo.pSetLayouts = &m_materialDescriptorSetLayout;

    if (vkAllocateDescriptorSets(m_context.getDevice(), &allocInfo, &descSet) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate material descriptor set");
    }

    Texture* albedo = material.albedoMap ? material.albedoMap : Texture::getWhite();
    Texture* normal = material.normalMap ? material.normalMap : Texture::getNormalDefault();
    Texture* roughness = material.roughnessMap ? material.roughnessMap : Texture::getWhite();
    Texture* metallic = material.metallicMap ? material.metallicMap : Texture::getBlack();
    Texture* ao = material.aoMap ? material.aoMap : Texture::getWhite();
    Texture* emissive = material.emissiveMap ? material.emissiveMap : Texture::getBlack();
    Texture* opacity = material.opacityMap ? material.opacityMap : Texture::getWhite();
    Texture* height = material.heightMap ? material.heightMap : Texture::getBlack();

    std::array<VkDescriptorImageInfo, 8> imageInfos{};
    imageInfos[0] = {albedo->getSampler(), albedo->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[1] = {normal->getSampler(), normal->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[2] = {roughness->getSampler(), roughness->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[3] = {metallic->getSampler(), metallic->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[4] = {ao->getSampler(), ao->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[5] = {emissive->getSampler(), emissive->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[6] = {opacity->getSampler(), opacity->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    imageInfos[7] = {height->getSampler(), height->getImageView(), VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};

    std::array<VkWriteDescriptorSet, 8> writes{};
    for (size_t i = 0; i < writes.size(); ++i) {
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet = descSet;
        writes[i].dstBinding = static_cast<u32>(i);
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        writes[i].descriptorCount = 1;
        writes[i].pImageInfo = &imageInfos[i];
    }

    vkUpdateDescriptorSets(m_context.getDevice(), static_cast<u32>(writes.size()), writes.data(), 0, nullptr);
    return descSet;
}

void Renderer::buildMaterialDescriptorSets() {
    m_materialDescriptorSets.clear();
    m_materialDescriptorSets["default"] = m_defaultMaterialDescriptorSet;

    if (!m_materialLibrary) {
        return;
    }

    for (const auto& [name, mat] : m_materialLibrary->getMaterials()) {
        if (!mat) continue;
        if (m_materialDescriptorSets.find(name) != m_materialDescriptorSets.end()) continue;
        m_materialDescriptorSets[name] = createMaterialDescriptorSetForMaterial(*mat);
    }
}

void Renderer::bindMaterialDescriptorSet(const std::string& materialName) {
    VkDescriptorSet set = m_defaultMaterialDescriptorSet;
    auto it = m_materialDescriptorSets.find(materialName);
    if (it != m_materialDescriptorSets.end()) {
        set = it->second;
    } else if (!materialName.empty()) {
        std::string lowered = materialName;
        std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
            return static_cast<char>(std::tolower(c));
        });

        if (lowered.find("wall") != std::string::npos) {
            set = m_materialDescriptorSets["drywall"];
        } else if (lowered.find("roof") != std::string::npos) {
            set = m_materialDescriptorSets["shingle"];
        } else if (lowered.find("window") != std::string::npos || lowered.find("glass") != std::string::npos) {
            set = m_materialDescriptorSets["glass"];
        } else if (lowered.find("door") != std::string::npos || lowered.find("wood") != std::string::npos) {
            set = m_materialDescriptorSets["wood"];
        } else if (lowered.find("metal") != std::string::npos || lowered.find("steel") != std::string::npos) {
            set = m_materialDescriptorSets["metal"];
        } else if (lowered.find("concrete") != std::string::npos) {
            set = m_materialDescriptorSets["concrete"];
        } else if (lowered.find("brick") != std::string::npos) {
            set = m_materialDescriptorSets["brick"];
        }
    }

    // Skip redundant descriptor set binds (reduces GPU state changes)
    if (set == m_lastBoundMaterialSet) {
        return;
    }
    m_lastBoundMaterialSet = set;

    vkCmdBindDescriptorSets(m_currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                            m_pipelineLayout, 1, 1, &set, 0, nullptr);
}

static std::string normalizeMaterialKey(const std::string& name) {
    std::string out;
    out.reserve(name.size());
    bool lastUnderscore = false;

    for (unsigned char c : name) {
        if (std::isalnum(c)) {
            out.push_back(static_cast<char>(std::tolower(c)));
            lastUnderscore = false;
        } else if (c == '_' || c == '-' || c == ' ' || c == '\t' || c == '/') {
            if (!lastUnderscore && !out.empty()) {
                out.push_back('_');
                lastUnderscore = true;
            }
        }
    }

    if (!out.empty() && out.back() == '_') {
        out.pop_back();
    }

    return out;
}

std::string Renderer::resolveMaterialName(const StructuralElement& element) const {
    auto hasMaterial = [&](const std::string& name) -> bool {
        return m_materialLibrary && m_materialLibrary->hasMaterial(name);
    };

    auto defaultForType = [&]() -> std::string {
        switch (element.type) {
            case ElementType::Wall:
                if (m_materialStyle == MaterialStyle::Realistic && hasMaterial("brick_red_01")) {
                    return "brick_red_01";
                }
                return "drywall";
            case ElementType::Door: return "wood";
            case ElementType::Window: return "glass";
            case ElementType::Floor: return "tile";
            case ElementType::Roof: return "shingle";
            case ElementType::Beam:
            case ElementType::Column:
                return "metal";
            default:
                return "default";
        }
    };

    auto mapKeyword = [&](const std::string& key) -> std::string {
        if (key.find("brick") != std::string::npos) {
            if (m_materialStyle == MaterialStyle::Realistic && hasMaterial("brick_red_01")) {
                return "brick_red_01";
            }
            return "brick";
        }
        if (key.find("concrete") != std::string::npos || key.find("cement") != std::string::npos ||
            key.find("stone") != std::string::npos) {
            return "concrete";
        }
        if (key.find("drywall") != std::string::npos || key.find("plaster") != std::string::npos ||
            key.find("gypsum") != std::string::npos || key.find("paint") != std::string::npos ||
            key.find("stucco") != std::string::npos || key.find("poly") != std::string::npos ||
            key.find("tyvek") != std::string::npos || key.find("membrane") != std::string::npos) {
            return "drywall";
        }
        if (key.find("wood") != std::string::npos || key.find("timber") != std::string::npos ||
            key.find("osb") != std::string::npos || key.find("plywood") != std::string::npos) {
            return "wood";
        }
        if (key.find("vinyl") != std::string::npos || key.find("siding") != std::string::npos) {
            if (m_materialStyle == MaterialStyle::Realistic && hasMaterial("brick_red_01")) {
                return "brick_red_01";
            }
            return "brick";
        }
        if (key.find("glass") != std::string::npos || key.find("glazing") != std::string::npos) {
            return "glass";
        }
        if (key.find("metal") != std::string::npos || key.find("steel") != std::string::npos ||
            key.find("aluminum") != std::string::npos) {
            return "metal";
        }
        if (key.find("tile") != std::string::npos || key.find("ceramic") != std::string::npos) {
            return "tile";
        }
        if (key.find("shingle") != std::string::npos || key.find("asphalt") != std::string::npos ||
            key.find("roof") != std::string::npos) {
            return "shingle";
        }

        return defaultForType();
    };

    if (!element.material.empty()) {
        if (hasMaterial(element.material)) {
            return element.material;
        }

        std::string normalized = normalizeMaterialKey(element.material);
        if (!normalized.empty() && hasMaterial(normalized)) {
            return normalized;
        }

        if (!normalized.empty()) {
            return mapKeyword(normalized);
        }
    }

    return defaultForType();
}

void Renderer::drawGrid(f32 size, f32 spacing) {
    (void)size; (void)spacing;
    mat4 transform = mat4(1.0f);
    PushConstants push{};
    push.model = transform;
    push.color = vec4(0.3f, 0.3f, 0.3f, 1.0f);

    vkCmdPushConstants(m_currentCommandBuffer, m_pipelineLayout,
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT | VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT | VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT,
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

    // Debug: count element types on first call per building change
    static std::string lastBuilding;
    if (building.name != lastBuilding) {
        lastBuilding = building.name;
        int doors = 0, windows = 0, walls = 0;
        for (const auto& e : elements) {
            if (e.type == ElementType::Door) doors++;
            else if (e.type == ElementType::Window) windows++;
            else if (e.type == ElementType::Wall) walls++;
        }
        std::cout << "[Renderer] Building: " << building.name << " - " << walls << " walls, " << doors << " doors, " << windows << " windows\n";
    }

    size_t index = 0;
    for (const auto& element : elements) {
        vec3 color = getElementColor(element, building, index);

        // Highlight selected elements with yellow/orange
        bool isSelected = selectedIndices.count(static_cast<int>(index)) > 0;
        if (isSelected) {
            color = vec3(1.0f, 0.8f, 0.2f);  // Yellow-orange highlight
        }
        // Bind material textures for this element (set 1)
        bindMaterialDescriptorSet(resolveMaterialName(element));

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
                // If door has custom mesh, render it directly
                if (element.mesh.hasData()) {
                    vec4 doorMat = vec4(0.0f, 0.75f, 1.0f, 0.0f);
                    drawCustomMeshWithMaterial(element.mesh, color, stressForShader, doorMat);
                    break;
                }

                // Generate door geometry
                float xExtent = element.end.x - element.start.x;
                float zExtent = element.end.z - element.start.z;
                float doorHeight = element.end.y - element.start.y;
                float doorDepth = element.depth > 0.1f ? element.depth : 0.5f;

                if (doorHeight <= 0.01f) break;

                float doorWidth = glm::length(vec2(xExtent, zExtent));
                if (doorWidth <= 0.01f) {
                    // Fallback: use element.width if extents are zero
                    doorWidth = element.width > 0.01f ? element.width : 3.0f;
                }

                // Calculate door position at bottom center of wall segment
                vec3 doorPos = vec3(
                    (element.start.x + element.end.x) * 0.5f,
                    element.start.y,  // Bottom of door
                    (element.start.z + element.end.z) * 0.5f
                );

                // Calculate rotation from extents (which are set from host wall direction)
                // The door mesh has width along X and depth (walkthrough) along Z
                // For the door width to align with wall direction, we use negative angle
                float angle = -std::atan2(zExtent, xExtent);

                // Create transform: translate to position, rotate to align with wall
                mat4 transform = glm::translate(mat4(1.0f), doorPos);
                transform = glm::rotate(transform, angle, vec3(0, 1, 0));

                // Wood door material
                vec4 doorMat = vec4(0.0f, 0.75f, 1.0f, 0.0f);

                // Create proper door mesh with frame, panel, and handle
                std::string key = "door_proper_" + std::to_string(static_cast<int>(doorWidth * 100)) + "_" +
                                 std::to_string(static_cast<int>(doorHeight * 100)) + "_" +
                                 std::to_string(static_cast<int>(doorDepth * 100));

                if (m_meshCache.find(key) == m_meshCache.end()) {
                    // createDoor expects position at bottom center, creates door from y=0 to y=height
                    auto [verts, indices] = Geometry::createDoor(
                        vec3(0), doorWidth, doorHeight, doorDepth, vec3(0.55f, 0.35f, 0.2f));
                    m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                }

                drawMeshWithMaterial(*m_meshCache[key], transform, color, stressForShader, doorMat);
                break;
            }

            case ElementType::Window:
                // Windows are rendered in a separate transparent pass below
                break;

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

    // Second pass: Render transparent windows with alpha blending
    Pipeline* transparentPipeline = m_outputLinearHDR ? m_hdrTransparentPipeline.get() : m_transparentPipeline.get();
    if (transparentPipeline) {
        m_context.beginDebugLabel(m_currentCommandBuffer, "Transparent Windows", {0.4f, 0.7f, 0.9f, 1.0f});
        transparentPipeline->bind(m_currentCommandBuffer);

        index = 0;
        for (const auto& element : elements) {
            if (element.type != ElementType::Window) {
                index++;
                continue;
            }

            bindMaterialDescriptorSet(resolveMaterialName(element));

            vec3 color = getElementColor(element, building, index);
            bool isSelected = selectedIndices.count(static_cast<int>(index)) > 0;
            if (isSelected) {
                color = vec3(1.0f, 0.8f, 0.2f);
            }
            f32 stressForShader = (m_vizMode == VisualizationMode::Structural) ? element.stress : 0.0f;

            // Generate window geometry
            float xExtent = element.end.x - element.start.x;
            float zExtent = element.end.z - element.start.z;
            float windowHeight = element.end.y - element.start.y;
            float windowDepth = element.depth > 0.01f ? element.depth : 0.3f;

            if (windowHeight <= 0.01f) {
                index++;
                continue;
            }

            float windowWidth = glm::length(vec2(xExtent, zExtent));
            if (windowWidth <= 0.01f) {
                index++;
                continue;
            }

            // Calculate window position at bottom center of wall segment
            vec3 windowPos = vec3(
                (element.start.x + element.end.x) * 0.5f,
                element.start.y,  // Bottom of window
                (element.start.z + element.end.z) * 0.5f
            );

            // Calculate rotation from extents (negate for proper alignment)
            float angle = -std::atan2(zExtent, xExtent);

            mat4 transform = glm::translate(mat4(1.0f), windowPos);
            transform = glm::rotate(transform, angle, vec3(0, 1, 0));

            // Glass material: very low roughness for transparency
            vec4 glassMat = vec4(0.0f, 0.1f, 1.0f, 0.0f);

            // Create proper window mesh with frame, glass, and mullions
            std::string key = "window_proper_" + std::to_string(static_cast<int>(windowWidth * 100)) + "_" +
                             std::to_string(static_cast<int>(windowHeight * 100)) + "_" +
                             std::to_string(static_cast<int>(windowDepth * 100));

            if (m_meshCache.find(key) == m_meshCache.end()) {
                // createWindow expects position at bottom center, creates window from y=0 to y=height
                auto [verts, indices] = Geometry::createWindow(
                    vec3(0), windowWidth, windowHeight, windowDepth, vec3(0.8f, 0.9f, 0.95f));
                m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
            }

            drawMeshWithMaterial(*m_meshCache[key], transform, color, stressForShader, glassMat);
            index++;
        }

        // Rebind opaque pipeline for subsequent draws
        if (m_vizMode == VisualizationMode::Wireframe) {
            if (m_tessellationEnabled && m_tessWireframePipeline) {
                m_tessWireframePipeline->bind(m_currentCommandBuffer);
            } else if (m_wireframePipeline) {
                m_wireframePipeline->bind(m_currentCommandBuffer);
            }
        } else {
            if (m_tessellationEnabled && m_tessPipeline) {
                m_tessPipeline->bind(m_currentCommandBuffer);
            } else if (m_pipeline) {
                m_pipeline->bind(m_currentCommandBuffer);
            }
        }

        m_context.endDebugLabel(m_currentCommandBuffer);
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

// =============================================================================
// High-Resolution Rendering Implementation
// =============================================================================

void Renderer::createHighResResources(u32 width, u32 height) {
    // Cleanup any existing resources
    cleanupHighResResources();

    m_highResWidth = width;
    m_highResHeight = height;

    VkDevice device = m_context.getDevice();

    // Create color image (RGBA8 for LDR output)
    VkImageCreateInfo imageInfo{};
    imageInfo.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.format = VK_FORMAT_R8G8B8A8_UNORM;
    imageInfo.extent = { width, height, 1 };
    imageInfo.mipLevels = 1;
    imageInfo.arrayLayers = 1;
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

    if (vkCreateImage(device, &imageInfo, nullptr, &m_highResImage) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res image");
    }

    // Allocate memory
    VkMemoryRequirements memReqs;
    vkGetImageMemoryRequirements(device, m_highResImage, &memReqs);

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(memReqs.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    if (vkAllocateMemory(device, &allocInfo, nullptr, &m_highResMemory) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate high-res image memory");
    }

    vkBindImageMemory(device, m_highResImage, m_highResMemory, 0);

    // Create image view
    VkImageViewCreateInfo viewInfo{};
    viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    viewInfo.image = m_highResImage;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = VK_FORMAT_R8G8B8A8_UNORM;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.baseArrayLayer = 0;
    viewInfo.subresourceRange.layerCount = 1;

    if (vkCreateImageView(device, &viewInfo, nullptr, &m_highResView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res image view");
    }

    // Create depth image
    VkFormat depthFormat = VK_FORMAT_D32_SFLOAT;
    VkImageCreateInfo depthImageInfo = imageInfo;
    depthImageInfo.format = depthFormat;
    depthImageInfo.usage = VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;

    if (vkCreateImage(device, &depthImageInfo, nullptr, &m_highResDepthImage) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res depth image");
    }

    vkGetImageMemoryRequirements(device, m_highResDepthImage, &memReqs);
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(memReqs.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    if (vkAllocateMemory(device, &allocInfo, nullptr, &m_highResDepthMemory) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate high-res depth memory");
    }

    vkBindImageMemory(device, m_highResDepthImage, m_highResDepthMemory, 0);

    viewInfo.image = m_highResDepthImage;
    viewInfo.format = depthFormat;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;

    if (vkCreateImageView(device, &viewInfo, nullptr, &m_highResDepthView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res depth view");
    }

    // Create render pass for high-res rendering (simple, no MSAA)
    VkAttachmentDescription colorAttachment{};
    colorAttachment.format = VK_FORMAT_R8G8B8A8_UNORM;
    colorAttachment.samples = VK_SAMPLE_COUNT_1_BIT;
    colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    colorAttachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    colorAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    colorAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    colorAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    colorAttachment.finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;

    VkAttachmentDescription depthAttachment{};
    depthAttachment.format = depthFormat;
    depthAttachment.samples = VK_SAMPLE_COUNT_1_BIT;
    depthAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    depthAttachment.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depthAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    depthAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    depthAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    depthAttachment.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkAttachmentReference colorRef{};
    colorRef.attachment = 0;
    colorRef.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

    VkAttachmentReference depthRef{};
    depthRef.attachment = 1;
    depthRef.layout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

    VkSubpassDescription subpass{};
    subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    subpass.colorAttachmentCount = 1;
    subpass.pColorAttachments = &colorRef;
    subpass.pDepthStencilAttachment = &depthRef;

    VkSubpassDependency dependency{};
    dependency.srcSubpass = VK_SUBPASS_EXTERNAL;
    dependency.dstSubpass = 0;
    dependency.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dependency.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
    dependency.srcAccessMask = 0;
    dependency.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

    std::array<VkAttachmentDescription, 2> attachments = { colorAttachment, depthAttachment };

    VkRenderPassCreateInfo renderPassInfo{};
    renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
    renderPassInfo.attachmentCount = static_cast<u32>(attachments.size());
    renderPassInfo.pAttachments = attachments.data();
    renderPassInfo.subpassCount = 1;
    renderPassInfo.pSubpasses = &subpass;
    renderPassInfo.dependencyCount = 1;
    renderPassInfo.pDependencies = &dependency;

    if (vkCreateRenderPass(device, &renderPassInfo, nullptr, &m_highResRenderPass) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res render pass");
    }

    // Create framebuffer
    std::array<VkImageView, 2> fbAttachments = { m_highResView, m_highResDepthView };

    VkFramebufferCreateInfo fbInfo{};
    fbInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
    fbInfo.renderPass = m_highResRenderPass;
    fbInfo.attachmentCount = static_cast<u32>(fbAttachments.size());
    fbInfo.pAttachments = fbAttachments.data();
    fbInfo.width = width;
    fbInfo.height = height;
    fbInfo.layers = 1;

    if (vkCreateFramebuffer(device, &fbInfo, nullptr, &m_highResFramebuffer) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create high-res framebuffer");
    }

    // Create single-sample pipeline for high-res rendering
    PipelineConfig highResConfig = PipelineConfig::defaultConfig();
    highResConfig.renderPass = m_highResRenderPass;
    highResConfig.pipelineLayout = m_pipelineLayout;
    highResConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
    highResConfig.multisample.sampleShadingEnable = VK_FALSE;

    m_highResPipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                    "shaders/structural.frag.spv", highResConfig);

    // Create high-res transparent pipeline for glass/windows
    PipelineConfig highResTransparentConfig = PipelineConfig::transparentConfig();
    highResTransparentConfig.renderPass = m_highResRenderPass;
    highResTransparentConfig.pipelineLayout = m_pipelineLayout;
    highResTransparentConfig.multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;

    m_highResTransparentPipeline = std::make_unique<Pipeline>(m_context, "shaders/structural.vert.spv",
                                                               "shaders/structural.frag.spv", highResTransparentConfig);

    std::cout << "[Renderer] High-res resources created: " << width << "x" << height << std::endl;
}

void Renderer::cleanupHighResResources() {
    VkDevice device = m_context.getDevice();

    // Destroy pipelines first (uses render pass)
    m_highResPipeline.reset();
    m_highResTransparentPipeline.reset();

    if (m_highResFramebuffer != VK_NULL_HANDLE) {
        vkDestroyFramebuffer(device, m_highResFramebuffer, nullptr);
        m_highResFramebuffer = VK_NULL_HANDLE;
    }
    if (m_highResRenderPass != VK_NULL_HANDLE) {
        vkDestroyRenderPass(device, m_highResRenderPass, nullptr);
        m_highResRenderPass = VK_NULL_HANDLE;
    }
    if (m_highResDepthView != VK_NULL_HANDLE) {
        vkDestroyImageView(device, m_highResDepthView, nullptr);
        m_highResDepthView = VK_NULL_HANDLE;
    }
    if (m_highResDepthImage != VK_NULL_HANDLE) {
        vkDestroyImage(device, m_highResDepthImage, nullptr);
        m_highResDepthImage = VK_NULL_HANDLE;
    }
    if (m_highResDepthMemory != VK_NULL_HANDLE) {
        vkFreeMemory(device, m_highResDepthMemory, nullptr);
        m_highResDepthMemory = VK_NULL_HANDLE;
    }
    if (m_highResView != VK_NULL_HANDLE) {
        vkDestroyImageView(device, m_highResView, nullptr);
        m_highResView = VK_NULL_HANDLE;
    }
    if (m_highResImage != VK_NULL_HANDLE) {
        vkDestroyImage(device, m_highResImage, nullptr);
        m_highResImage = VK_NULL_HANDLE;
    }
    if (m_highResMemory != VK_NULL_HANDLE) {
        vkFreeMemory(device, m_highResMemory, nullptr);
        m_highResMemory = VK_NULL_HANDLE;
    }
}

void Renderer::copyHighResImageToBuffer() {
    VkDevice device = m_context.getDevice();
    size_t imageSize = m_highResWidth * m_highResHeight * 4;

    // Create staging buffer
    VkBuffer stagingBuffer;
    VkDeviceMemory stagingMemory;

    VkBufferCreateInfo bufferInfo{};
    bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bufferInfo.size = imageSize;
    bufferInfo.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    vkCreateBuffer(device, &bufferInfo, nullptr, &stagingBuffer);

    VkMemoryRequirements memReqs;
    vkGetBufferMemoryRequirements(device, stagingBuffer, &memReqs);

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(
        memReqs.memoryTypeBits,
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT
    );

    vkAllocateMemory(device, &allocInfo, nullptr, &stagingMemory);
    vkBindBufferMemory(device, stagingBuffer, stagingMemory, 0);

    // Copy image to buffer
    VkCommandBuffer cmd = m_context.beginSingleTimeCommands();

    VkBufferImageCopy region{};
    region.bufferOffset = 0;
    region.bufferRowLength = 0;
    region.bufferImageHeight = 0;
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.mipLevel = 0;
    region.imageSubresource.baseArrayLayer = 0;
    region.imageSubresource.layerCount = 1;
    region.imageOffset = { 0, 0, 0 };
    region.imageExtent = { m_highResWidth, m_highResHeight, 1 };

    vkCmdCopyImageToBuffer(cmd, m_highResImage, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, stagingBuffer, 1, &region);

    m_context.endSingleTimeCommands(cmd);

    // Map and copy to CPU memory
    m_highResPixels.resize(imageSize);
    void* data;
    vkMapMemory(device, stagingMemory, 0, imageSize, 0, &data);
    memcpy(m_highResPixels.data(), data, imageSize);
    vkUnmapMemory(device, stagingMemory);

    // Cleanup
    vkDestroyBuffer(device, stagingBuffer, nullptr);
    vkFreeMemory(device, stagingMemory, nullptr);
}

// Halton sequence for sub-pixel jitter (better than random for AA)
static float halton(int index, int base) {
    float result = 0.0f;
    float f = 1.0f / static_cast<float>(base);
    int i = index;
    while (i > 0) {
        result += f * static_cast<float>(i % base);
        i /= base;
        f /= static_cast<float>(base);
    }
    return result;
}

bool Renderer::renderHighRes(
    const std::vector<StructuralElement>& elements,
    const Building& building,
    u32 width,
    u32 height,
    int samples,
    float brightness,
    std::function<void(float)> progressCallback
) {
    std::cout << "[Renderer] Starting high-res render: " << width << "x" << height << " with " << samples << " samples" << std::endl;

    try {
        // Create resources at target resolution
        createHighResResources(width, height);

        // Wait for any pending operations
        m_context.waitIdle();

        // Initialize HDR accumulation buffer for multi-sample AA
        size_t pixelCount = static_cast<size_t>(width) * height;
        std::vector<float> accumBuffer(pixelCount * 4, 0.0f);  // RGBA float accumulation

        float aspect = static_cast<float>(width) / static_cast<float>(height);
        mat4 baseProj = m_camera.getProjectionMatrix(aspect);
        baseProj[1][1] *= -1; // Vulkan Y flip

        // Create fence for synchronization
        VkFence fence;
        VkFenceCreateInfo fenceInfo{};
        fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        vkCreateFence(m_context.getDevice(), &fenceInfo, nullptr, &fence);

        // Render each sample with sub-pixel jitter
        for (int sampleIdx = 0; sampleIdx < samples; ++sampleIdx) {
            // Report progress
            if (progressCallback) {
                float progress = static_cast<float>(sampleIdx) / static_cast<float>(samples) * 0.9f;
                progressCallback(progress);
            }

            std::cout << "[Renderer] Rendering sample " << (sampleIdx + 1) << "/" << samples << std::endl;

            // Compute sub-pixel jitter using Halton sequence
            float jitterX = 0.0f;
            float jitterY = 0.0f;
            if (samples > 1) {
                // Halton(2) and Halton(3) for X and Y jitter
                jitterX = halton(sampleIdx + 1, 2) - 0.5f;
                jitterY = halton(sampleIdx + 1, 3) - 0.5f;
            }

            // Apply jitter to projection matrix (sub-pixel offset)
            mat4 jitteredProj = baseProj;
            if (samples > 1) {
                // Jitter in NDC space: offset by fraction of pixel
                float pixelWidth = 2.0f / static_cast<float>(width);
                float pixelHeight = 2.0f / static_cast<float>(height);
                jitteredProj[2][0] += jitterX * pixelWidth;
                jitteredProj[2][1] += jitterY * pixelHeight;
            }

            // Allocate command buffer
            VkCommandBufferAllocateInfo allocInfo{};
            allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
            allocInfo.commandPool = m_context.getCommandPool();
            allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
            allocInfo.commandBufferCount = 1;

            VkCommandBuffer cmd;
            vkAllocateCommandBuffers(m_context.getDevice(), &allocInfo, &cmd);

            VkCommandBufferBeginInfo beginInfo{};
            beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
            beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
            vkBeginCommandBuffer(cmd, &beginInfo);

            // Begin render pass
            VkRenderPassBeginInfo renderPassInfo{};
            renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
            renderPassInfo.renderPass = m_highResRenderPass;
            renderPassInfo.framebuffer = m_highResFramebuffer;
            renderPassInfo.renderArea.offset = { 0, 0 };
            renderPassInfo.renderArea.extent = { width, height };

            std::array<VkClearValue, 2> clearValues{};
            clearValues[0].color = { { 0.529f, 0.808f, 0.922f, 1.0f } };  // Sky blue background
            clearValues[1].depthStencil = { 1.0f, 0 };

            renderPassInfo.clearValueCount = static_cast<u32>(clearValues.size());
            renderPassInfo.pClearValues = clearValues.data();

            vkCmdBeginRenderPass(cmd, &renderPassInfo, VK_SUBPASS_CONTENTS_INLINE);

            // Set viewport and scissor
            VkViewport viewport{};
            viewport.x = 0.0f;
            viewport.y = 0.0f;
            viewport.width = static_cast<float>(width);
            viewport.height = static_cast<float>(height);
            viewport.minDepth = 0.0f;
            viewport.maxDepth = 1.0f;
            vkCmdSetViewport(cmd, 0, 1, &viewport);

            VkRect2D scissor{};
            scissor.offset = { 0, 0 };
            scissor.extent = { width, height };
            vkCmdSetScissor(cmd, 0, 1, &scissor);

            // Update uniform buffer with jittered projection
            UniformBufferObject ubo{};
            ubo.view = m_camera.getViewMatrix();
            ubo.proj = jitteredProj;
            ubo.lightViewProj = m_shadowMap ? m_shadowMap->getLightViewProj() : mat4(1.0f);
            ubo.lightDirection = vec4(m_lightDirection, 0.0f);
            ubo.clipPlane = m_clippingEnabled ? m_clipPlane : vec4(0.0f);
            ubo.time = m_time;
            ubo.shadowBias = m_shadowBias;
            ubo.enableClipping = m_clippingEnabled ? 1 : 0;
            ubo.enableShadows = m_shadowsEnabled ? 1 : 0;
            ubo.outputLinearHDR = 0;
            // Apply user-controlled brightness to compensate for missing bloom
            ubo.exposure = getExposure() * brightness;
            // Also boost material brightness slightly for similar effect
            ubo.materialParams = vec4(m_materialUVScale, m_normalStrength, m_materialBrightness + (brightness - 1.0f) * 0.1f, m_materialContrast);
            ubo.materialParams2 = vec4(m_materialSaturation, m_materialRoughnessOffset, m_materialMetallicOffset, m_materialAOStrength);
            ubo.materialTint = vec4(m_materialTint, 1.0f);

            memcpy(m_uniformBuffersMapped[0], &ubo, sizeof(ubo));

            // Set current command buffer so draw functions use the right one
            VkCommandBuffer oldCmd = m_currentCommandBuffer;
            m_currentCommandBuffer = cmd;

            // Bind high-res pipeline (single-sample) and descriptor sets
            m_highResPipeline->bind(cmd);
            vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, m_pipelineLayout, 0, 1, &m_descriptorSets[0], 0, nullptr);

            // Draw all elements
            for (size_t i = 0; i < elements.size(); ++i) {
                const auto& elem = elements[i];
                vec3 color = getElementColor(elem, building, i);

                // Bind material
                std::string matName = resolveMaterialName(elem);
                bindMaterialDescriptorSet(matName);

                // Get material preset
                auto preset = getMaterialForElement(elem.type);
                vec4 material(preset.metallic, preset.roughness, preset.ao, preset.emission);

                // Compute stress for shader
                f32 stressForShader = (m_vizMode == VisualizationMode::Structural) ? elem.stress : 0.0f;

                // Draw based on element type (matching main render loop logic)
                switch (elem.type) {
                    case ElementType::Beam:
                        drawBeam(elem.start, elem.end, elem.width, elem.depth, color, stressForShader, elem.deflection);
                        break;
                    case ElementType::Column: {
                        float colHeight = elem.end.y - elem.start.y;
                        drawColumnWithMaterial(elem.start, elem.width, elem.depth, colHeight, color, stressForShader, material);
                        break;
                    }
                    case ElementType::Floor:
                        if (elem.mesh.hasData()) {
                            drawCustomMesh(elem.mesh, color, stressForShader);
                        } else {
                            vec3 center = (elem.start + elem.end) * 0.5f;
                            center.y = elem.start.y;
                            float thickness = elem.end.y - elem.start.y;
                            drawFloor(center, elem.end.x - elem.start.x, elem.end.z - elem.start.z, thickness, color, stressForShader);
                        }
                        break;
                    case ElementType::Wall: {
                        if (elem.mesh.hasData()) {
                            drawCustomMesh(elem.mesh, color, stressForShader);
                        } else {
                            // Generate wall geometry - supports diagonal walls
                            float xExtent = elem.end.x - elem.start.x;
                            float zExtent = elem.end.z - elem.start.z;
                            float wallHeight = elem.end.y - elem.start.y;
                            bool isDiagonal = std::abs(xExtent) > 0.1f && std::abs(zExtent) > 0.1f;
                            vec4 wallMat = vec4(m_wallMetallic, m_wallRoughness, m_wallAO, m_wallEmission);

                            if (isDiagonal) {
                                float midHeight = elem.start.y + wallHeight * 0.5f;
                                vec3 wallStart = vec3(elem.start.x, midHeight, elem.start.z);
                                vec3 wallEnd = vec3(elem.end.x, midHeight, elem.end.z);
                                float thickness = elem.depth > 0.01f ? elem.depth : 0.5f;

                                std::string key = "diagwall_" + std::to_string(xExtent) + "_" +
                                                 std::to_string(zExtent) + "_" + std::to_string(wallHeight) + "_" +
                                                 std::to_string(thickness);
                                if (m_meshCache.find(key) == m_meshCache.end()) {
                                    auto [verts, indices] = Geometry::createBeam(wallStart, wallEnd, thickness, wallHeight, vec3(1.0f));
                                    m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                                }
                                drawMeshWithMaterial(*m_meshCache[key], mat4(1.0f), color, stressForShader, wallMat);
                            } else {
                                vec3 center = (elem.start + elem.end) * 0.5f;
                                center.y = elem.start.y;
                                float wallThickness = elem.depth > 0.01f ? elem.depth : 0.5f;

                                if (std::abs(xExtent) > std::abs(zExtent)) {
                                    drawColumnWithMaterial(center, std::abs(xExtent), wallThickness, wallHeight, color, stressForShader, wallMat);
                                } else {
                                    drawColumnWithMaterial(center, wallThickness, std::abs(zExtent), wallHeight, color, stressForShader, wallMat);
                                }
                            }
                        }
                        break;
                    }
                    case ElementType::Door: {
                        if (elem.mesh.hasData()) {
                            drawCustomMeshWithMaterial(elem.mesh, color, stressForShader, material);
                        } else {
                            // Generate door geometry
                            float xExtent = elem.end.x - elem.start.x;
                            float zExtent = elem.end.z - elem.start.z;
                            float doorHeight = elem.end.y - elem.start.y;
                            float doorDepth = elem.depth > 0.1f ? elem.depth : 0.5f;

                            if (doorHeight > 0.01f) {
                                float doorWidth = glm::length(vec2(xExtent, zExtent));
                                if (doorWidth <= 0.01f) doorWidth = elem.width > 0.01f ? elem.width : 3.0f;

                                vec3 doorPos = vec3((elem.start.x + elem.end.x) * 0.5f, elem.start.y,
                                                    (elem.start.z + elem.end.z) * 0.5f);
                                float angle = -std::atan2(zExtent, xExtent);
                                mat4 transform = glm::translate(mat4(1.0f), doorPos);
                                transform = glm::rotate(transform, angle, vec3(0, 1, 0));

                                vec4 doorMat = vec4(0.0f, 0.75f, 1.0f, 0.0f);
                                std::string key = "door_proper_" + std::to_string(static_cast<int>(doorWidth * 100)) + "_" +
                                                 std::to_string(static_cast<int>(doorHeight * 100)) + "_" +
                                                 std::to_string(static_cast<int>(doorDepth * 100));
                                if (m_meshCache.find(key) == m_meshCache.end()) {
                                    auto [verts, indices] = Geometry::createDoor(vec3(0), doorWidth, doorHeight, doorDepth, vec3(0.55f, 0.35f, 0.2f));
                                    m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                                }
                                drawMeshWithMaterial(*m_meshCache[key], transform, color, stressForShader, doorMat);
                            }
                        }
                        break;
                    }
                    case ElementType::Window:
                        // Windows rendered in transparent pass below
                        break;
                    case ElementType::Roof: {
                        vec4 roofMat = vec4(m_roofMetallic, m_roofRoughness, m_roofAO, m_roofEmission);
                        if (elem.mesh.hasData()) {
                            drawCustomMeshWithMaterial(elem.mesh, color, stressForShader, roofMat);
                        } else {
                            float roofWidth = std::abs(elem.end.x - elem.start.x);
                            float roofDepthZ = std::abs(elem.end.z - elem.start.z);
                            float roofThickness = elem.end.y - elem.start.y;
                            if (roofThickness < 0.1f) roofThickness = 0.5f;

                            vec3 center = (elem.start + elem.end) * 0.5f;
                            center.y = elem.start.y;

                            std::string key = "roof_" + std::to_string(roofWidth) + "_" + std::to_string(roofDepthZ) + "_" + std::to_string(roofThickness);
                            if (m_meshCache.find(key) == m_meshCache.end()) {
                                auto [verts, indices] = Geometry::createFloorSlab(vec3(0), roofWidth, roofDepthZ, roofThickness);
                                m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                            }
                            mat4 roofTransform = glm::translate(mat4(1.0f), center);
                            drawMeshWithMaterial(*m_meshCache[key], roofTransform, color, stressForShader, roofMat);
                        }
                        break;
                    }
                    default:
                        break;
                }
            }

            // Note: Sky is skipped in high-res render as the sky pipeline uses
            // the swapchain render pass (MSAA) and different command buffer.
            // A solid background color is used instead (set in clear values).

            // Second pass: Render transparent windows with alpha blending
            if (m_highResTransparentPipeline) {
                m_highResTransparentPipeline->bind(cmd);

                for (size_t i = 0; i < elements.size(); ++i) {
                    const auto& elem = elements[i];
                    if (elem.type != ElementType::Window) continue;

                    vec3 color = getElementColor(elem, building, i);
                    f32 stressForShader = (m_vizMode == VisualizationMode::Structural) ? elem.stress : 0.0f;

                    // Bind material
                    std::string matName = resolveMaterialName(elem);
                    bindMaterialDescriptorSet(matName);

                    // Generate window geometry
                    float xExtent = elem.end.x - elem.start.x;
                    float zExtent = elem.end.z - elem.start.z;
                    float winHeight = elem.end.y - elem.start.y;
                    float winDepth = elem.depth > 0.01f ? elem.depth : 0.15f;

                    if (winHeight > 0.01f) {
                        float winWidth = glm::length(vec2(xExtent, zExtent));
                        if (winWidth <= 0.01f) winWidth = elem.width > 0.01f ? elem.width : 1.2f;

                        vec3 winPos = vec3((elem.start.x + elem.end.x) * 0.5f, elem.start.y,
                                           (elem.start.z + elem.end.z) * 0.5f);
                        float angle = -std::atan2(zExtent, xExtent);
                        mat4 transform = glm::translate(mat4(1.0f), winPos);
                        transform = glm::rotate(transform, angle, vec3(0, 1, 0));

                        vec4 glassMat = vec4(0.0f, 0.1f, 1.0f, 0.0f);  // Smooth glass
                        std::string key = "window_proper_" + std::to_string(static_cast<int>(winWidth * 100)) + "_" +
                                         std::to_string(static_cast<int>(winHeight * 100)) + "_" +
                                         std::to_string(static_cast<int>(winDepth * 100));
                        if (m_meshCache.find(key) == m_meshCache.end()) {
                            auto [verts, indices] = Geometry::createWindow(vec3(0), winWidth, winHeight, winDepth, vec3(0.8f, 0.9f, 0.95f));
                            m_meshCache[key] = std::make_unique<Mesh>(m_context, verts, indices);
                        }
                        drawMeshWithMaterial(*m_meshCache[key], transform, color, stressForShader, glassMat);
                    }
                }
            }

            vkCmdEndRenderPass(cmd);
            vkEndCommandBuffer(cmd);

            // Restore the original command buffer
            m_currentCommandBuffer = oldCmd;

            // Submit and wait
            VkSubmitInfo submitInfo{};
            submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
            submitInfo.commandBufferCount = 1;
            submitInfo.pCommandBuffers = &cmd;

            vkResetFences(m_context.getDevice(), 1, &fence);
            vkQueueSubmit(m_context.getGraphicsQueue(), 1, &submitInfo, fence);
            vkWaitForFences(m_context.getDevice(), 1, &fence, VK_TRUE, UINT64_MAX);

            vkFreeCommandBuffers(m_context.getDevice(), m_context.getCommandPool(), 1, &cmd);

            // Copy this sample's result to CPU
            copyHighResImageToBuffer();

            // Accumulate this sample into the float buffer
            for (size_t p = 0; p < pixelCount; ++p) {
                accumBuffer[p * 4 + 0] += static_cast<float>(m_highResPixels[p * 4 + 0]);
                accumBuffer[p * 4 + 1] += static_cast<float>(m_highResPixels[p * 4 + 1]);
                accumBuffer[p * 4 + 2] += static_cast<float>(m_highResPixels[p * 4 + 2]);
                accumBuffer[p * 4 + 3] += static_cast<float>(m_highResPixels[p * 4 + 3]);
            }
        }

        vkDestroyFence(m_context.getDevice(), fence, nullptr);

        // Ensure all GPU work is complete before returning to normal rendering
        m_context.waitIdle();

        // Reset frame tracking to avoid stale fence references
        m_currentFrame = 0;
        m_imagesInFlight.assign(m_context.getSwapchainImageCount(), VK_NULL_HANDLE);

        // Average the accumulated samples and convert back to 8-bit
        float invSamples = 1.0f / static_cast<float>(samples);
        for (size_t p = 0; p < pixelCount; ++p) {
            m_highResPixels[p * 4 + 0] = static_cast<u8>(std::min(255.0f, accumBuffer[p * 4 + 0] * invSamples));
            m_highResPixels[p * 4 + 1] = static_cast<u8>(std::min(255.0f, accumBuffer[p * 4 + 1] * invSamples));
            m_highResPixels[p * 4 + 2] = static_cast<u8>(std::min(255.0f, accumBuffer[p * 4 + 2] * invSamples));
            m_highResPixels[p * 4 + 3] = static_cast<u8>(std::min(255.0f, accumBuffer[p * 4 + 3] * invSamples));
        }

        // Store HDR data for potential EXR export
        m_highResHDRPixels.resize(pixelCount * 4);
        for (size_t p = 0; p < pixelCount; ++p) {
            m_highResHDRPixels[p * 4 + 0] = accumBuffer[p * 4 + 0] * invSamples / 255.0f;
            m_highResHDRPixels[p * 4 + 1] = accumBuffer[p * 4 + 1] * invSamples / 255.0f;
            m_highResHDRPixels[p * 4 + 2] = accumBuffer[p * 4 + 2] * invSamples / 255.0f;
            m_highResHDRPixels[p * 4 + 3] = accumBuffer[p * 4 + 3] * invSamples / 255.0f;
        }

        if (progressCallback) progressCallback(1.0f);

        std::cout << "[Renderer] High-res render complete with " << samples << " samples" << std::endl;
        return true;

    } catch (const std::exception& e) {
        std::cerr << "[Renderer] High-res render failed: " << e.what() << std::endl;
        return false;
    }
}

bool Renderer::saveHighResPNG(const std::string& filepath) {
    if (m_highResPixels.empty() || m_highResWidth == 0 || m_highResHeight == 0) {
        std::cerr << "[Renderer] No high-res image to save" << std::endl;
        return false;
    }

    // Create directory if needed
    std::filesystem::path path(filepath);
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path());
    }

    // stb_image_write expects top-to-bottom, which is what we have
    int result = stbi_write_png(
        filepath.c_str(),
        static_cast<int>(m_highResWidth),
        static_cast<int>(m_highResHeight),
        4,  // RGBA
        m_highResPixels.data(),
        static_cast<int>(m_highResWidth * 4)
    );

    if (result) {
        std::cout << "[Renderer] Saved high-res image to: " << filepath << std::endl;
        return true;
    } else {
        std::cerr << "[Renderer] Failed to save PNG: " << filepath << std::endl;
        return false;
    }
}

bool Renderer::saveHighResEXR(const std::string& filepath) {
    // EXR export requires additional library (tinyexr or OpenEXR)
    // For now, fall back to PNG with a warning
    std::cerr << "[Renderer] EXR export not yet implemented, saving as PNG instead" << std::endl;
    std::string pngPath = filepath;
    size_t extPos = pngPath.rfind(".exr");
    if (extPos != std::string::npos) {
        pngPath.replace(extPos, 4, ".png");
    }
    return saveHighResPNG(pngPath);
}

} // namespace arch
