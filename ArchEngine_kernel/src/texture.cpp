#include "texture.hpp"
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <cstring>

#include "stb_image.h"

namespace arch {

// Static default textures
std::unique_ptr<Texture> Texture::s_white;
std::unique_ptr<Texture> Texture::s_black;
std::unique_ptr<Texture> Texture::s_normalDefault;

Texture::Texture(VulkanContext& context)
    : m_context(context) {
}

Texture::~Texture() {
    if (m_sampler != VK_NULL_HANDLE) {
        vkDestroySampler(m_context.getDevice(), m_sampler, nullptr);
    }
    if (m_imageView != VK_NULL_HANDLE) {
        vkDestroyImageView(m_context.getDevice(), m_imageView, nullptr);
    }
    if (m_image != VK_NULL_HANDLE) {
        vkDestroyImage(m_context.getDevice(), m_image, nullptr);
    }
    if (m_memory != VK_NULL_HANDLE) {
        vkFreeMemory(m_context.getDevice(), m_memory, nullptr);
    }
}

bool Texture::loadFromFile(const std::string& filepath, bool sRGB) {
    int width, height, channels;
    stbi_uc* pixels = stbi_load(filepath.c_str(), &width, &height, &channels, STBI_rgb_alpha);

    if (!pixels) {
        std::cerr << "[Texture] Failed to load: " << filepath << " - " << stbi_failure_reason() << std::endl;
        return false;
    }

    VkFormat format = sRGB ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM;
    createImage(pixels, width, height, format);

    stbi_image_free(pixels);

    m_width = width;
    m_height = height;
    m_loaded = true;

    std::cout << "[Texture] Loaded: " << filepath << " (" << width << "x" << height << ")" << std::endl;
    return true;
}

void Texture::createSolidColor(vec4 color, bool sRGB) {
    u8 pixels[4] = {
        static_cast<u8>(color.r * 255.0f),
        static_cast<u8>(color.g * 255.0f),
        static_cast<u8>(color.b * 255.0f),
        static_cast<u8>(color.a * 255.0f)
    };

    VkFormat format = sRGB ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM;
    createImage(pixels, 1, 1, format);

    m_width = 1;
    m_height = 1;
    m_loaded = true;
}

void Texture::createImage(const void* pixels, u32 width, u32 height, VkFormat format) {
    VkDeviceSize imageSize = width * height * 4;

    // Create staging buffer
    VkBuffer stagingBuffer;
    VkDeviceMemory stagingMemory;
    m_context.createBuffer(imageSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           stagingBuffer, stagingMemory);

    // Copy pixel data to staging buffer
    void* data;
    vkMapMemory(m_context.getDevice(), stagingMemory, 0, imageSize, 0, &data);
    memcpy(data, pixels, imageSize);
    vkUnmapMemory(m_context.getDevice(), stagingMemory);

    // Create image
    m_context.createImage(width, height, format, VK_IMAGE_TILING_OPTIMAL,
                          VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT,
                          VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                          m_image, m_memory);

    // Transition to transfer destination
    m_context.transitionImageLayout(m_image, format,
                                    VK_IMAGE_LAYOUT_UNDEFINED,
                                    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);

    // Copy buffer to image
    m_context.copyBufferToImage(stagingBuffer, m_image, width, height);

    // Transition to shader read
    m_context.transitionImageLayout(m_image, format,
                                    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                    VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);

    // Cleanup staging buffer
    vkDestroyBuffer(m_context.getDevice(), stagingBuffer, nullptr);
    vkFreeMemory(m_context.getDevice(), stagingMemory, nullptr);

    // Create image view
    m_imageView = m_context.createImageView(m_image, format, VK_IMAGE_ASPECT_COLOR_BIT);

    // Create sampler
    createSampler();
}

void Texture::createSampler() {
    VkSamplerCreateInfo samplerInfo{};
    samplerInfo.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
    samplerInfo.magFilter = VK_FILTER_LINEAR;
    samplerInfo.minFilter = VK_FILTER_LINEAR;
    samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_REPEAT;
    samplerInfo.anisotropyEnable = VK_TRUE;
    samplerInfo.maxAnisotropy = 16.0f;
    samplerInfo.borderColor = VK_BORDER_COLOR_INT_OPAQUE_BLACK;
    samplerInfo.unnormalizedCoordinates = VK_FALSE;
    samplerInfo.compareEnable = VK_FALSE;
    samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
    samplerInfo.mipLodBias = 0.0f;
    samplerInfo.minLod = 0.0f;
    samplerInfo.maxLod = 0.0f;

    if (vkCreateSampler(m_context.getDevice(), &samplerInfo, nullptr, &m_sampler) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create texture sampler");
    }
}

void Texture::createDefaultTextures(VulkanContext& context) {
    // White texture (default albedo)
    s_white = std::make_unique<Texture>(context);
    s_white->createSolidColor(vec4(1.0f, 1.0f, 1.0f, 1.0f), true);

    // Black texture (default metallic/emission)
    s_black = std::make_unique<Texture>(context);
    s_black->createSolidColor(vec4(0.0f, 0.0f, 0.0f, 1.0f), false);

    // Default normal map (flat surface pointing up in tangent space)
    s_normalDefault = std::make_unique<Texture>(context);
    s_normalDefault->createSolidColor(vec4(0.5f, 0.5f, 1.0f, 1.0f), false);

    std::cout << "[Texture] Created default textures" << std::endl;
}

Texture* Texture::getWhite() { return s_white.get(); }
Texture* Texture::getBlack() { return s_black.get(); }
Texture* Texture::getNormalDefault() { return s_normalDefault.get(); }

// ============================================================================
// MaterialLibrary
// ============================================================================

MaterialLibrary::MaterialLibrary(VulkanContext& context)
    : m_context(context) {
    // Initialize default textures if not already done
    if (!Texture::getWhite()) {
        Texture::createDefaultTextures(context);
    }

    // Setup default material
    m_defaultMaterial.name = "default";
    m_defaultMaterial.albedoMap = Texture::getWhite();
    m_defaultMaterial.normalMap = Texture::getNormalDefault();
    m_defaultMaterial.roughnessMap = Texture::getWhite();  // White = rough
    m_defaultMaterial.metallicMap = Texture::getBlack();   // Black = non-metallic
    m_defaultMaterial.aoMap = Texture::getWhite();         // White = no occlusion
    m_defaultMaterial.albedoColor = vec3(0.8f);
    m_defaultMaterial.roughness = 0.5f;
    m_defaultMaterial.metallic = 0.0f;
}

MaterialLibrary::~MaterialLibrary() {
    m_materials.clear();
    m_textures.clear();
}

Material* MaterialLibrary::loadMaterial(const std::string& name, const std::string& directory) {
    auto mat = std::make_unique<Material>();
    mat->name = name;

    namespace fs = std::filesystem;

    // Try to load each texture type
    auto tryLoad = [&](const std::string& suffix, bool sRGB) -> Texture* {
        for (const auto& ext : {".png", ".jpg", ".jpeg", ".tga"}) {
            std::string path = directory + "/" + suffix + ext;
            if (fs::exists(path)) {
                auto tex = std::make_unique<Texture>(m_context);
                if (tex->loadFromFile(path, sRGB)) {
                    auto* ptr = tex.get();
                    m_textures[name + "_" + suffix] = std::move(tex);
                    return ptr;
                }
            }
        }
        return nullptr;
    };

    mat->albedoMap = tryLoad("albedo", true);
    if (!mat->albedoMap) mat->albedoMap = tryLoad("diffuse", true);
    if (!mat->albedoMap) mat->albedoMap = tryLoad("basecolor", true);
    if (!mat->albedoMap) mat->albedoMap = Texture::getWhite();

    mat->normalMap = tryLoad("normal", false);
    if (!mat->normalMap) mat->normalMap = Texture::getNormalDefault();

    mat->roughnessMap = tryLoad("roughness", false);
    if (!mat->roughnessMap) mat->roughnessMap = Texture::getWhite();

    mat->metallicMap = tryLoad("metallic", false);
    if (!mat->metallicMap) mat->metallicMap = tryLoad("metalness", false);
    if (!mat->metallicMap) mat->metallicMap = Texture::getBlack();

    mat->aoMap = tryLoad("ao", false);
    if (!mat->aoMap) mat->aoMap = tryLoad("ambient_occlusion", false);
    if (!mat->aoMap) mat->aoMap = Texture::getWhite();

    auto* ptr = mat.get();
    m_materials[name] = std::move(mat);

    std::cout << "[MaterialLibrary] Loaded material: " << name << std::endl;
    return ptr;
}

Material* MaterialLibrary::createSolidMaterial(const std::string& name, vec3 albedo, f32 roughness, f32 metallic) {
    auto mat = std::make_unique<Material>();
    mat->name = name;
    mat->albedoColor = albedo;
    mat->roughness = roughness;
    mat->metallic = metallic;

    // Create solid color albedo texture
    auto tex = std::make_unique<Texture>(m_context);
    tex->createSolidColor(vec4(albedo, 1.0f), true);
    mat->albedoMap = tex.get();
    m_textures[name + "_albedo"] = std::move(tex);

    mat->normalMap = Texture::getNormalDefault();
    mat->roughnessMap = Texture::getWhite();
    mat->metallicMap = Texture::getBlack();
    mat->aoMap = Texture::getWhite();

    auto* ptr = mat.get();
    m_materials[name] = std::move(mat);
    return ptr;
}

Material* MaterialLibrary::getMaterial(const std::string& name) {
    auto it = m_materials.find(name);
    return (it != m_materials.end()) ? it->second.get() : &m_defaultMaterial;
}

void MaterialLibrary::createBuiltinMaterials() {
    // Concrete - gray, rough, non-metallic
    createSolidMaterial("concrete", vec3(0.6f, 0.58f, 0.55f), 0.9f, 0.0f);

    // Brick - reddish, rough
    createSolidMaterial("brick", vec3(0.7f, 0.35f, 0.25f), 0.85f, 0.0f);

    // Wood - brownish, medium rough
    createSolidMaterial("wood", vec3(0.55f, 0.35f, 0.2f), 0.7f, 0.0f);

    // Drywall/Plaster - off-white, rough
    createSolidMaterial("drywall", vec3(0.9f, 0.88f, 0.85f), 0.95f, 0.0f);

    // Metal - gray, smooth, metallic
    createSolidMaterial("metal", vec3(0.8f, 0.8f, 0.8f), 0.3f, 1.0f);

    // Glass - slight tint, very smooth
    createSolidMaterial("glass", vec3(0.9f, 0.95f, 1.0f), 0.05f, 0.0f);

    // Tile - white, smooth
    createSolidMaterial("tile", vec3(0.95f, 0.95f, 0.95f), 0.2f, 0.0f);

    // Asphalt shingle (roof)
    createSolidMaterial("shingle", vec3(0.25f, 0.25f, 0.28f), 0.8f, 0.0f);

    std::cout << "[MaterialLibrary] Created " << m_materials.size() << " builtin materials" << std::endl;
}

} // namespace arch
