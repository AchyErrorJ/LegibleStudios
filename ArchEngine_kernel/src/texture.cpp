#include "texture.hpp"
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <cstring>

#include "stb_image.h"
#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace arch {

// Static default textures
std::unique_ptr<Texture> Texture::s_white;
std::unique_ptr<Texture> Texture::s_black;
std::unique_ptr<Texture> Texture::s_grey;
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
    if (m_context.supportsSamplerAnisotropy()) {
        samplerInfo.anisotropyEnable = VK_TRUE;
        samplerInfo.maxAnisotropy = m_context.getMaxSamplerAnisotropy();
    } else {
        samplerInfo.anisotropyEnable = VK_FALSE;
        samplerInfo.maxAnisotropy = 1.0f;
    }
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

    // Grey texture (0.5 - default height map, means no displacement)
    s_grey = std::make_unique<Texture>(context);
    s_grey->createSolidColor(vec4(0.5f, 0.5f, 0.5f, 1.0f), false);

    // Default normal map (flat surface pointing up in tangent space)
    s_normalDefault = std::make_unique<Texture>(context);
    s_normalDefault->createSolidColor(vec4(0.5f, 0.5f, 1.0f, 1.0f), false);

    std::cout << "[Texture] Created default textures" << std::endl;
}

Texture* Texture::getWhite() { return s_white.get(); }
Texture* Texture::getBlack() { return s_black.get(); }
Texture* Texture::getGrey() { return s_grey.get(); }
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
    m_defaultMaterial.emissiveMap = Texture::getBlack();
    m_defaultMaterial.opacityMap = Texture::getWhite();
    m_defaultMaterial.heightMap = Texture::getGrey();  // Grey = 0.5 = no displacement
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

    mat->emissiveMap = tryLoad("emissive", true);
    if (!mat->emissiveMap) mat->emissiveMap = tryLoad("emission", true);
    if (!mat->emissiveMap) mat->emissiveMap = tryLoad("emit", true);
    if (!mat->emissiveMap) mat->emissiveMap = Texture::getBlack();

    mat->opacityMap = tryLoad("opacity", false);
    if (!mat->opacityMap) mat->opacityMap = tryLoad("alpha", false);
    if (!mat->opacityMap) mat->opacityMap = Texture::getWhite();

    // Height/displacement map (linear grayscale)
    mat->heightMap = tryLoad("height", false);
    if (!mat->heightMap) mat->heightMap = tryLoad("displacement", false);
    if (!mat->heightMap) mat->heightMap = tryLoad("bump", false);
    if (!mat->heightMap) mat->heightMap = Texture::getGrey();   // Grey (0.5) = no displacement

    auto* ptr = mat.get();
    m_materials[name] = std::move(mat);

    std::cout << "[MaterialLibrary] Loaded material: " << name << std::endl;
    return ptr;
}

u32 MaterialLibrary::loadMaterialsFromDirectory(const std::string& rootDirectory) {
    namespace fs = std::filesystem;

    if (!fs::exists(rootDirectory) || !fs::is_directory(rootDirectory)) {
        std::cout << "[MaterialLibrary] Materials directory not found: " << rootDirectory << std::endl;
        return 0;
    }

    u32 loaded = 0;
    for (const auto& entry : fs::directory_iterator(rootDirectory)) {
        if (!entry.is_directory()) continue;

        std::string name = entry.path().filename().string();
        if (m_materials.find(name) != m_materials.end()) {
            continue;
        }

        if (loadMaterial(name, entry.path().string())) {
            loaded++;
        }
    }

    if (loaded > 0) {
        std::cout << "[MaterialLibrary] Loaded " << loaded << " materials from " << rootDirectory << std::endl;
    }

    return loaded;
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
    mat->emissiveMap = Texture::getBlack();
    mat->opacityMap = Texture::getWhite();
    mat->heightMap = Texture::getGrey();  // Grey (0.5) = no displacement

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

void MaterialLibrary::loadMaterialSettings(const std::string& settingsPath) {
    namespace fs = std::filesystem;
    if (!fs::exists(settingsPath)) return;

    try {
        std::ifstream file(settingsPath);
        json data = json::parse(file);

        if (!data.contains("materials")) return;

        for (auto& [name, settings] : data["materials"].items()) {
            auto it = m_materials.find(name);
            if (it == m_materials.end()) continue;

            Material* mat = it->second.get();

            if (settings.contains("uvScale")) {
                auto& uv = settings["uvScale"];
                if (uv.is_array() && uv.size() >= 2) {
                    mat->uvScale = vec2(uv[0].get<float>(), uv[1].get<float>());
                } else if (uv.is_number()) {
                    float s = uv.get<float>();
                    mat->uvScale = vec2(s, s);
                }
            }
            if (settings.contains("brightness"))
                mat->brightness = settings["brightness"].get<float>();
            if (settings.contains("contrast"))
                mat->contrast = settings["contrast"].get<float>();
            if (settings.contains("saturation"))
                mat->saturation = settings["saturation"].get<float>();
            if (settings.contains("normalStrength"))
                mat->normalStrength = settings["normalStrength"].get<float>();
            if (settings.contains("roughnessOffset"))
                mat->roughnessOffset = settings["roughnessOffset"].get<float>();
            if (settings.contains("metallicOffset"))
                mat->metallicOffset = settings["metallicOffset"].get<float>();
            if (settings.contains("aoStrength"))
                mat->aoStrength = settings["aoStrength"].get<float>();
            if (settings.contains("tint")) {
                auto& t = settings["tint"];
                if (t.is_array() && t.size() >= 3) {
                    mat->tint = vec3(t[0].get<float>(), t[1].get<float>(), t[2].get<float>());
                }
            }
        }
        std::cout << "[MaterialLibrary] Loaded material settings from " << settingsPath << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "[MaterialLibrary] Error loading settings: " << e.what() << std::endl;
    }
}

void MaterialLibrary::saveMaterialSettings(const std::string& settingsPath) {
    json data;
    data["materials"] = json::object();

    for (const auto& [name, mat] : m_materials) {
        json settings;
        settings["uvScale"] = {mat->uvScale.x, mat->uvScale.y};
        settings["brightness"] = mat->brightness;
        settings["contrast"] = mat->contrast;
        settings["saturation"] = mat->saturation;
        settings["normalStrength"] = mat->normalStrength;
        settings["roughnessOffset"] = mat->roughnessOffset;
        settings["metallicOffset"] = mat->metallicOffset;
        settings["aoStrength"] = mat->aoStrength;
        settings["tint"] = {mat->tint.r, mat->tint.g, mat->tint.b};
        data["materials"][name] = settings;
    }

    try {
        std::ofstream file(settingsPath);
        file << data.dump(2);
        std::cout << "[MaterialLibrary] Saved material settings to " << settingsPath << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "[MaterialLibrary] Error saving settings: " << e.what() << std::endl;
    }
}

void MaterialLibrary::saveMaterialSettings(Material* material, const std::string& settingsPath) {
    namespace fs = std::filesystem;
    json data;

    // Load existing settings if file exists
    if (fs::exists(settingsPath)) {
        try {
            std::ifstream file(settingsPath);
            data = json::parse(file);
        } catch (...) {
            data = json::object();
        }
    }

    if (!data.contains("materials")) {
        data["materials"] = json::object();
    }

    json settings;
    settings["uvScale"] = {material->uvScale.x, material->uvScale.y};
    settings["brightness"] = material->brightness;
    settings["contrast"] = material->contrast;
    settings["saturation"] = material->saturation;
    settings["normalStrength"] = material->normalStrength;
    settings["roughnessOffset"] = material->roughnessOffset;
    settings["metallicOffset"] = material->metallicOffset;
    settings["aoStrength"] = material->aoStrength;
    settings["tint"] = {material->tint.r, material->tint.g, material->tint.b};
    data["materials"][material->name] = settings;

    try {
        std::ofstream file(settingsPath);
        file << data.dump(2);
    } catch (const std::exception& e) {
        std::cerr << "[MaterialLibrary] Error saving material: " << e.what() << std::endl;
    }
}

} // namespace arch
