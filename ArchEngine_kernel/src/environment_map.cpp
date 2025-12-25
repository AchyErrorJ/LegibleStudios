#include "environment_map.hpp"
#include <stdexcept>
#include <cstring>
#include <cmath>
#include <vector>

#define STB_IMAGE_IMPLEMENTATION
#include "../external/stb_image.h"

namespace arch {

EnvironmentMap::EnvironmentMap(VulkanContext& context) : m_context(context) {
    createSampler();
}

EnvironmentMap::~EnvironmentMap() {
    cleanup();
}

void EnvironmentMap::cleanup() {
    if (m_sampler != VK_NULL_HANDLE) {
        vkDestroySampler(m_context.getDevice(), m_sampler, nullptr);
        m_sampler = VK_NULL_HANDLE;
    }
    if (m_cubemapView != VK_NULL_HANDLE) {
        vkDestroyImageView(m_context.getDevice(), m_cubemapView, nullptr);
        m_cubemapView = VK_NULL_HANDLE;
    }
    if (m_cubemapImage != VK_NULL_HANDLE) {
        vkDestroyImage(m_context.getDevice(), m_cubemapImage, nullptr);
        m_cubemapImage = VK_NULL_HANDLE;
    }
    if (m_cubemapMemory != VK_NULL_HANDLE) {
        vkFreeMemory(m_context.getDevice(), m_cubemapMemory, nullptr);
        m_cubemapMemory = VK_NULL_HANDLE;
    }
    m_loaded = false;
}

void EnvironmentMap::createSampler() {
    VkSamplerCreateInfo samplerInfo{};
    samplerInfo.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    samplerInfo.magFilter = VK_FILTER_LINEAR;
    samplerInfo.minFilter = VK_FILTER_LINEAR;
    samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
    samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    samplerInfo.anisotropyEnable = VK_TRUE;
    samplerInfo.maxAnisotropy = 16.0f;
    samplerInfo.borderColor = VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK;
    samplerInfo.compareEnable = VK_FALSE;
    samplerInfo.minLod = 0.0f;
    samplerInfo.maxLod = 1.0f;

    if (vkCreateSampler(m_context.getDevice(), &samplerInfo, nullptr, &m_sampler) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create environment map sampler");
    }
}

bool EnvironmentMap::loadFromFile(const std::string& filepath) {
    // Enable HDR loading
    stbi_set_flip_vertically_on_load(true);

    int width, height, channels;
    float* hdrData = stbi_loadf(filepath.c_str(), &width, &height, &channels, 3);

    if (!hdrData) {
        return false;
    }

    createCubemapFromEquirectangular(hdrData, width, height);
    stbi_image_free(hdrData);

    m_loaded = true;
    return true;
}

void EnvironmentMap::createProceduralSky() {
    // Create a simple procedural sky cubemap
    const u32 size = m_cubemapSize;
    std::vector<float> faceData(size * size * 4);  // RGBA float

    // Cleanup existing if any
    if (m_cubemapImage != VK_NULL_HANDLE) {
        m_context.waitIdle();
        vkDestroyImageView(m_context.getDevice(), m_cubemapView, nullptr);
        vkDestroyImage(m_context.getDevice(), m_cubemapImage, nullptr);
        vkFreeMemory(m_context.getDevice(), m_cubemapMemory, nullptr);
    }

    // Create cubemap image
    VkImageCreateInfo imageInfo{};
    imageInfo.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.format = VK_FORMAT_R16G16B16A16_SFLOAT;  // HDR format
    imageInfo.extent = {size, size, 1};
    imageInfo.mipLevels = 1;
    imageInfo.arrayLayers = 6;  // 6 faces
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.flags = VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT;

    if (vkCreateImage(m_context.getDevice(), &imageInfo, nullptr, &m_cubemapImage) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create cubemap image");
    }

    // Allocate memory
    VkMemoryRequirements memReqs;
    vkGetImageMemoryRequirements(m_context.getDevice(), m_cubemapImage, &memReqs);

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(memReqs.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    if (vkAllocateMemory(m_context.getDevice(), &allocInfo, nullptr, &m_cubemapMemory) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate cubemap memory");
    }
    vkBindImageMemory(m_context.getDevice(), m_cubemapImage, m_cubemapMemory, 0);

    // Create staging buffer for all 6 faces
    VkDeviceSize faceSize = size * size * 4 * sizeof(uint16_t);  // RGBA16F per face
    VkDeviceSize totalSize = faceSize * 6;

    VkBuffer stagingBuffer;
    VkDeviceMemory stagingMemory;
    m_context.createBuffer(totalSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           stagingBuffer, stagingMemory);

    // Map staging buffer
    void* data;
    vkMapMemory(m_context.getDevice(), stagingMemory, 0, totalSize, 0, &data);
    uint16_t* halfData = static_cast<uint16_t*>(data);

    // Helper to convert float to half
    auto floatToHalf = [](float f) -> uint16_t {
        uint32_t x = *reinterpret_cast<uint32_t*>(&f);
        uint32_t sign = (x >> 16) & 0x8000;
        int32_t exp = ((x >> 23) & 0xFF) - 127 + 15;
        uint32_t mant = x & 0x007FFFFF;

        if (exp <= 0) {
            return static_cast<uint16_t>(sign);
        } else if (exp >= 31) {
            return static_cast<uint16_t>(sign | 0x7C00);
        }
        return static_cast<uint16_t>(sign | (exp << 10) | (mant >> 13));
    };

    // Generate each face
    for (int face = 0; face < 6; ++face) {
        uint16_t* facePtr = halfData + (face * size * size * 4);

        for (u32 y = 0; y < size; ++y) {
            for (u32 x = 0; x < size; ++x) {
                float u = (static_cast<float>(x) + 0.5f) / size * 2.0f - 1.0f;
                float v = (static_cast<float>(y) + 0.5f) / size * 2.0f - 1.0f;

                vec3 dir = getCubemapDirection(face, u, v);
                dir = glm::normalize(dir);

                // Procedural sky color based on direction
                vec3 color;
                if (dir.y > 0.0f) {
                    // Sky
                    vec3 zenith = vec3(0.4f, 0.6f, 0.9f);
                    vec3 horizon = vec3(0.7f, 0.8f, 0.95f);
                    float t = std::pow(dir.y, 0.8f);
                    color = glm::mix(horizon, zenith, t);
                } else {
                    // Ground
                    vec3 ground = vec3(0.35f, 0.45f, 0.3f);
                    vec3 groundFar = vec3(0.4f, 0.5f, 0.45f);
                    float t = std::pow(-dir.y, 0.5f);
                    color = glm::mix(groundFar, ground, t);
                }

                u32 idx = (y * size + x) * 4;
                facePtr[idx + 0] = floatToHalf(color.r);
                facePtr[idx + 1] = floatToHalf(color.g);
                facePtr[idx + 2] = floatToHalf(color.b);
                facePtr[idx + 3] = floatToHalf(1.0f);
            }
        }
    }

    vkUnmapMemory(m_context.getDevice(), stagingMemory);

    // Transition image and copy data
    VkCommandBuffer cmd = m_context.beginSingleTimeCommands();

    // Transition to transfer dst
    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.image = m_cubemapImage;
    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.baseMipLevel = 0;
    barrier.subresourceRange.levelCount = 1;
    barrier.subresourceRange.baseArrayLayer = 0;
    barrier.subresourceRange.layerCount = 6;
    barrier.srcAccessMask = 0;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;

    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    // Copy each face
    std::vector<VkBufferImageCopy> copyRegions(6);
    for (int face = 0; face < 6; ++face) {
        copyRegions[face].bufferOffset = face * faceSize;
        copyRegions[face].bufferRowLength = 0;
        copyRegions[face].bufferImageHeight = 0;
        copyRegions[face].imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        copyRegions[face].imageSubresource.mipLevel = 0;
        copyRegions[face].imageSubresource.baseArrayLayer = face;
        copyRegions[face].imageSubresource.layerCount = 1;
        copyRegions[face].imageOffset = {0, 0, 0};
        copyRegions[face].imageExtent = {size, size, 1};
    }

    vkCmdCopyBufferToImage(cmd, stagingBuffer, m_cubemapImage, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                           static_cast<u32>(copyRegions.size()), copyRegions.data());

    // Transition to shader read
    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    m_context.endSingleTimeCommands(cmd);

    // Cleanup staging
    vkDestroyBuffer(m_context.getDevice(), stagingBuffer, nullptr);
    vkFreeMemory(m_context.getDevice(), stagingMemory, nullptr);

    // Create image view
    VkImageViewCreateInfo viewInfo{};
    viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    viewInfo.image = m_cubemapImage;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_CUBE;
    viewInfo.format = VK_FORMAT_R16G16B16A16_SFLOAT;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.baseArrayLayer = 0;
    viewInfo.subresourceRange.layerCount = 6;

    if (vkCreateImageView(m_context.getDevice(), &viewInfo, nullptr, &m_cubemapView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create cubemap image view");
    }

    m_loaded = true;
}

void EnvironmentMap::createCubemapFromEquirectangular(const float* hdrData, int width, int height) {
    const u32 size = m_cubemapSize;

    // Cleanup existing if any
    if (m_cubemapImage != VK_NULL_HANDLE) {
        m_context.waitIdle();
        vkDestroyImageView(m_context.getDevice(), m_cubemapView, nullptr);
        vkDestroyImage(m_context.getDevice(), m_cubemapImage, nullptr);
        vkFreeMemory(m_context.getDevice(), m_cubemapMemory, nullptr);
    }

    // Create cubemap image
    VkImageCreateInfo imageInfo{};
    imageInfo.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.format = VK_FORMAT_R16G16B16A16_SFLOAT;
    imageInfo.extent = {size, size, 1};
    imageInfo.mipLevels = 1;
    imageInfo.arrayLayers = 6;
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.flags = VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT;

    if (vkCreateImage(m_context.getDevice(), &imageInfo, nullptr, &m_cubemapImage) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create cubemap image");
    }

    VkMemoryRequirements memReqs;
    vkGetImageMemoryRequirements(m_context.getDevice(), m_cubemapImage, &memReqs);

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memReqs.size;
    allocInfo.memoryTypeIndex = m_context.findMemoryType(memReqs.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);

    if (vkAllocateMemory(m_context.getDevice(), &allocInfo, nullptr, &m_cubemapMemory) != VK_SUCCESS) {
        throw std::runtime_error("Failed to allocate cubemap memory");
    }
    vkBindImageMemory(m_context.getDevice(), m_cubemapImage, m_cubemapMemory, 0);

    // Create staging buffer
    VkDeviceSize faceSize = size * size * 4 * sizeof(uint16_t);
    VkDeviceSize totalSize = faceSize * 6;

    VkBuffer stagingBuffer;
    VkDeviceMemory stagingMemory;
    m_context.createBuffer(totalSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           stagingBuffer, stagingMemory);

    void* data;
    vkMapMemory(m_context.getDevice(), stagingMemory, 0, totalSize, 0, &data);
    uint16_t* halfData = static_cast<uint16_t*>(data);

    auto floatToHalf = [](float f) -> uint16_t {
        uint32_t x = *reinterpret_cast<uint32_t*>(&f);
        uint32_t sign = (x >> 16) & 0x8000;
        int32_t exp = ((x >> 23) & 0xFF) - 127 + 15;
        uint32_t mant = x & 0x007FFFFF;
        if (exp <= 0) return static_cast<uint16_t>(sign);
        if (exp >= 31) return static_cast<uint16_t>(sign | 0x7C00);
        return static_cast<uint16_t>(sign | (exp << 10) | (mant >> 13));
    };

    // Sample equirectangular for each face
    for (int face = 0; face < 6; ++face) {
        uint16_t* facePtr = halfData + (face * size * size * 4);

        for (u32 y = 0; y < size; ++y) {
            for (u32 x = 0; x < size; ++x) {
                float u = (static_cast<float>(x) + 0.5f) / size * 2.0f - 1.0f;
                float v = (static_cast<float>(y) + 0.5f) / size * 2.0f - 1.0f;

                vec3 dir = glm::normalize(getCubemapDirection(face, u, v));

                // Convert direction to equirectangular UV
                float phi = std::atan2(dir.z, dir.x);
                float theta = std::asin(glm::clamp(dir.y, -1.0f, 1.0f));

                float eqU = (phi + glm::pi<float>()) / (2.0f * glm::pi<float>());
                float eqV = (theta + glm::pi<float>() * 0.5f) / glm::pi<float>();

                // Sample HDR data (bilinear)
                int px = static_cast<int>(eqU * width) % width;
                int py = static_cast<int>((1.0f - eqV) * height) % height;
                if (py < 0) py = 0;
                if (py >= height) py = height - 1;

                int srcIdx = (py * width + px) * 3;
                float r = hdrData[srcIdx + 0];
                float g = hdrData[srcIdx + 1];
                float b = hdrData[srcIdx + 2];

                u32 idx = (y * size + x) * 4;
                facePtr[idx + 0] = floatToHalf(r);
                facePtr[idx + 1] = floatToHalf(g);
                facePtr[idx + 2] = floatToHalf(b);
                facePtr[idx + 3] = floatToHalf(1.0f);
            }
        }
    }

    vkUnmapMemory(m_context.getDevice(), stagingMemory);

    // Transfer to GPU
    VkCommandBuffer cmd = m_context.beginSingleTimeCommands();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.image = m_cubemapImage;
    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.baseMipLevel = 0;
    barrier.subresourceRange.levelCount = 1;
    barrier.subresourceRange.baseArrayLayer = 0;
    barrier.subresourceRange.layerCount = 6;
    barrier.srcAccessMask = 0;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;

    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    std::vector<VkBufferImageCopy> copyRegions(6);
    for (int face = 0; face < 6; ++face) {
        copyRegions[face].bufferOffset = face * faceSize;
        copyRegions[face].bufferRowLength = 0;
        copyRegions[face].bufferImageHeight = 0;
        copyRegions[face].imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        copyRegions[face].imageSubresource.mipLevel = 0;
        copyRegions[face].imageSubresource.baseArrayLayer = face;
        copyRegions[face].imageSubresource.layerCount = 1;
        copyRegions[face].imageOffset = {0, 0, 0};
        copyRegions[face].imageExtent = {size, size, 1};
    }

    vkCmdCopyBufferToImage(cmd, stagingBuffer, m_cubemapImage, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                           static_cast<u32>(copyRegions.size()), copyRegions.data());

    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &barrier);

    m_context.endSingleTimeCommands(cmd);

    vkDestroyBuffer(m_context.getDevice(), stagingBuffer, nullptr);
    vkFreeMemory(m_context.getDevice(), stagingMemory, nullptr);

    // Create image view
    VkImageViewCreateInfo viewInfo{};
    viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    viewInfo.image = m_cubemapImage;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_CUBE;
    viewInfo.format = VK_FORMAT_R16G16B16A16_SFLOAT;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.baseArrayLayer = 0;
    viewInfo.subresourceRange.layerCount = 6;

    if (vkCreateImageView(m_context.getDevice(), &viewInfo, nullptr, &m_cubemapView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create cubemap image view");
    }
}

vec3 EnvironmentMap::getCubemapDirection(int face, float u, float v) {
    // Standard cubemap face directions
    switch (face) {
        case 0: return vec3( 1.0f, -v,    -u);     // +X
        case 1: return vec3(-1.0f, -v,     u);     // -X
        case 2: return vec3( u,     1.0f,  v);     // +Y
        case 3: return vec3( u,    -1.0f, -v);     // -Y
        case 4: return vec3( u,    -v,     1.0f);  // +Z
        case 5: return vec3(-u,    -v,    -1.0f);  // -Z
        default: return vec3(0.0f, 1.0f, 0.0f);
    }
}

VkDescriptorImageInfo EnvironmentMap::getDescriptorInfo() const {
    VkDescriptorImageInfo info{};
    info.sampler = m_sampler;
    info.imageView = m_cubemapView;
    info.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    return info;
}

} // namespace arch
