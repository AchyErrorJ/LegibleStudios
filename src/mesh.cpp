#include "mesh.hpp"
#include <stdexcept>
#include <cstring>

namespace arch {

Mesh::Mesh(VulkanContext& context, const std::vector<Vertex>& vertices,
           const std::vector<u32>& indices)
    : m_context(context), m_vertexCount(static_cast<u32>(vertices.size())),
      m_indexCount(static_cast<u32>(indices.size())) {

    createVertexBuffer(vertices);
    createIndexBuffer(indices);
}

Mesh::~Mesh() {
    if (m_indexBuffer != VK_NULL_HANDLE) {
        vkDestroyBuffer(m_context.getDevice(), m_indexBuffer, nullptr);
        vkFreeMemory(m_context.getDevice(), m_indexBufferMemory, nullptr);
    }
    if (m_vertexBuffer != VK_NULL_HANDLE) {
        vkDestroyBuffer(m_context.getDevice(), m_vertexBuffer, nullptr);
        vkFreeMemory(m_context.getDevice(), m_vertexBufferMemory, nullptr);
    }
}

Mesh::Mesh(Mesh&& other) noexcept
    : m_context(other.m_context),
      m_vertexBuffer(other.m_vertexBuffer),
      m_vertexBufferMemory(other.m_vertexBufferMemory),
      m_indexBuffer(other.m_indexBuffer),
      m_indexBufferMemory(other.m_indexBufferMemory),
      m_vertexCount(other.m_vertexCount),
      m_indexCount(other.m_indexCount) {

    other.m_vertexBuffer = VK_NULL_HANDLE;
    other.m_vertexBufferMemory = VK_NULL_HANDLE;
    other.m_indexBuffer = VK_NULL_HANDLE;
    other.m_indexBufferMemory = VK_NULL_HANDLE;
}

Mesh& Mesh::operator=(Mesh&& other) noexcept {
    if (this != &other) {
        // Clean up existing resources
        if (m_indexBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(m_context.getDevice(), m_indexBuffer, nullptr);
            vkFreeMemory(m_context.getDevice(), m_indexBufferMemory, nullptr);
        }
        if (m_vertexBuffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(m_context.getDevice(), m_vertexBuffer, nullptr);
            vkFreeMemory(m_context.getDevice(), m_vertexBufferMemory, nullptr);
        }

        // Move resources
        m_vertexBuffer = other.m_vertexBuffer;
        m_vertexBufferMemory = other.m_vertexBufferMemory;
        m_indexBuffer = other.m_indexBuffer;
        m_indexBufferMemory = other.m_indexBufferMemory;
        m_vertexCount = other.m_vertexCount;
        m_indexCount = other.m_indexCount;

        other.m_vertexBuffer = VK_NULL_HANDLE;
        other.m_vertexBufferMemory = VK_NULL_HANDLE;
        other.m_indexBuffer = VK_NULL_HANDLE;
        other.m_indexBufferMemory = VK_NULL_HANDLE;
    }
    return *this;
}

void Mesh::bind(VkCommandBuffer commandBuffer) {
    VkBuffer buffers[] = {m_vertexBuffer};
    VkDeviceSize offsets[] = {0};
    vkCmdBindVertexBuffers(commandBuffer, 0, 1, buffers, offsets);
    vkCmdBindIndexBuffer(commandBuffer, m_indexBuffer, 0, VK_INDEX_TYPE_UINT32);
}

void Mesh::draw(VkCommandBuffer commandBuffer) {
    vkCmdDrawIndexed(commandBuffer, m_indexCount, 1, 0, 0, 0);
}

void Mesh::createVertexBuffer(const std::vector<Vertex>& vertices) {
    VkDeviceSize bufferSize = sizeof(Vertex) * vertices.size();

    // Staging buffer
    VkBuffer stagingBuffer;
    VkDeviceMemory stagingBufferMemory;
    m_context.createBuffer(bufferSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           stagingBuffer, stagingBufferMemory);

    // Copy data to staging buffer
    void* data;
    vkMapMemory(m_context.getDevice(), stagingBufferMemory, 0, bufferSize, 0, &data);
    std::memcpy(data, vertices.data(), bufferSize);
    vkUnmapMemory(m_context.getDevice(), stagingBufferMemory);

    // Create device-local buffer
    m_context.createBuffer(bufferSize,
                           VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
                           VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                           m_vertexBuffer, m_vertexBufferMemory);

    // Copy from staging to device
    m_context.copyBuffer(stagingBuffer, m_vertexBuffer, bufferSize);

    // Cleanup staging buffer
    vkDestroyBuffer(m_context.getDevice(), stagingBuffer, nullptr);
    vkFreeMemory(m_context.getDevice(), stagingBufferMemory, nullptr);
}

void Mesh::createIndexBuffer(const std::vector<u32>& indices) {
    VkDeviceSize bufferSize = sizeof(u32) * indices.size();

    // Staging buffer
    VkBuffer stagingBuffer;
    VkDeviceMemory stagingBufferMemory;
    m_context.createBuffer(bufferSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           stagingBuffer, stagingBufferMemory);

    // Copy data
    void* data;
    vkMapMemory(m_context.getDevice(), stagingBufferMemory, 0, bufferSize, 0, &data);
    std::memcpy(data, indices.data(), bufferSize);
    vkUnmapMemory(m_context.getDevice(), stagingBufferMemory);

    // Create device-local buffer
    m_context.createBuffer(bufferSize,
                           VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_INDEX_BUFFER_BIT,
                           VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                           m_indexBuffer, m_indexBufferMemory);

    m_context.copyBuffer(stagingBuffer, m_indexBuffer, bufferSize);

    vkDestroyBuffer(m_context.getDevice(), stagingBuffer, nullptr);
    vkFreeMemory(m_context.getDevice(), stagingBufferMemory, nullptr);
}

// Geometry generation functions
namespace Geometry {

std::pair<std::vector<Vertex>, std::vector<u32>>
createBeam(vec3 start, vec3 end, f32 width, f32 height, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    // Beam direction and perpendicular vectors
    vec3 dir = glm::normalize(end - start);
    vec3 up = vec3(0, 1, 0);

    // Handle vertical beams
    if (std::abs(glm::dot(dir, up)) > 0.99f) {
        up = vec3(1, 0, 0);
    }

    vec3 right = glm::normalize(glm::cross(dir, up));
    vec3 localUp = glm::normalize(glm::cross(right, dir));

    f32 hw = width * 0.5f;
    f32 hh = height * 0.5f;

    // 8 corners of the beam box
    vec3 corners[8] = {
        start - right * hw - localUp * hh,  // 0: back-bottom-left
        start + right * hw - localUp * hh,  // 1: back-bottom-right
        start + right * hw + localUp * hh,  // 2: back-top-right
        start - right * hw + localUp * hh,  // 3: back-top-left
        end - right * hw - localUp * hh,    // 4: front-bottom-left
        end + right * hw - localUp * hh,    // 5: front-bottom-right
        end + right * hw + localUp * hh,    // 6: front-top-right
        end - right * hw + localUp * hh,    // 7: front-top-left
    };

    // Generate 6 faces with proper normals
    auto addFace = [&](u32 i0, u32 i1, u32 i2, u32 i3, vec3 normal) {
        u32 baseIndex = static_cast<u32>(vertices.size());
        vertices.push_back({corners[i0], normal, color});
        vertices.push_back({corners[i1], normal, color});
        vertices.push_back({corners[i2], normal, color});
        vertices.push_back({corners[i3], normal, color});

        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 3);
    };

    addFace(0, 1, 2, 3, -dir);      // Back face
    addFace(5, 4, 7, 6, dir);        // Front face
    addFace(4, 0, 3, 7, -right);     // Left face
    addFace(1, 5, 6, 2, right);      // Right face
    addFace(3, 2, 6, 7, localUp);    // Top face
    addFace(4, 5, 1, 0, -localUp);   // Bottom face

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createColumn(vec3 position, f32 width, f32 depth, f32 height, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 hw = width * 0.5f;
    f32 hd = depth * 0.5f;

    // 8 corners of the column
    vec3 corners[8] = {
        position + vec3(-hw, 0, -hd),       // 0: bottom-back-left
        position + vec3(hw, 0, -hd),        // 1: bottom-back-right
        position + vec3(hw, 0, hd),         // 2: bottom-front-right
        position + vec3(-hw, 0, hd),        // 3: bottom-front-left
        position + vec3(-hw, height, -hd),  // 4: top-back-left
        position + vec3(hw, height, -hd),   // 5: top-back-right
        position + vec3(hw, height, hd),    // 6: top-front-right
        position + vec3(-hw, height, hd),   // 7: top-front-left
    };

    auto addFace = [&](u32 i0, u32 i1, u32 i2, u32 i3, vec3 normal) {
        u32 baseIndex = static_cast<u32>(vertices.size());
        vertices.push_back({corners[i0], normal, color});
        vertices.push_back({corners[i1], normal, color});
        vertices.push_back({corners[i2], normal, color});
        vertices.push_back({corners[i3], normal, color});

        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 3);
    };

    addFace(0, 1, 5, 4, vec3(0, 0, -1));  // Back
    addFace(2, 3, 7, 6, vec3(0, 0, 1));   // Front
    addFace(3, 0, 4, 7, vec3(-1, 0, 0));  // Left
    addFace(1, 2, 6, 5, vec3(1, 0, 0));   // Right
    addFace(4, 5, 6, 7, vec3(0, 1, 0));   // Top
    addFace(3, 2, 1, 0, vec3(0, -1, 0));  // Bottom

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createFloorSlab(vec3 position, f32 width, f32 depth, f32 thickness, vec3 color) {
    return createColumn(position - vec3(0, thickness, 0), width, depth, thickness, color);
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createDeflectedBeam(vec3 start, vec3 end, f32 width, f32 height,
                    f32 deflection, u32 segments, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    vec3 dir = end - start;
    f32 length = glm::length(dir);
    dir = glm::normalize(dir);

    vec3 up = vec3(0, 1, 0);
    if (std::abs(glm::dot(dir, up)) > 0.99f) {
        up = vec3(1, 0, 0);
    }

    vec3 right = glm::normalize(glm::cross(dir, up));
    vec3 localUp = glm::normalize(glm::cross(right, dir));

    f32 hw = width * 0.5f;
    f32 hh = height * 0.5f;

    // Generate segments along the beam with parabolic deflection
    for (u32 i = 0; i <= segments; ++i) {
        f32 t = static_cast<f32>(i) / static_cast<f32>(segments);
        vec3 pos = start + dir * (length * t);

        // Parabolic deflection: max at center, zero at ends
        f32 deflectionFactor = 4.0f * t * (1.0f - t);  // Parabola
        pos -= localUp * (deflection * deflectionFactor);

        // Add 4 vertices for this cross-section
        vertices.push_back({pos - right * hw - localUp * hh, -localUp, color});
        vertices.push_back({pos + right * hw - localUp * hh, -localUp, color});
        vertices.push_back({pos + right * hw + localUp * hh, localUp, color});
        vertices.push_back({pos - right * hw + localUp * hh, localUp, color});
    }

    // Generate indices for the segments
    for (u32 i = 0; i < segments; ++i) {
        u32 base = i * 4;

        // Bottom face
        indices.push_back(base + 0); indices.push_back(base + 4); indices.push_back(base + 5);
        indices.push_back(base + 0); indices.push_back(base + 5); indices.push_back(base + 1);

        // Right face
        indices.push_back(base + 1); indices.push_back(base + 5); indices.push_back(base + 6);
        indices.push_back(base + 1); indices.push_back(base + 6); indices.push_back(base + 2);

        // Top face
        indices.push_back(base + 2); indices.push_back(base + 6); indices.push_back(base + 7);
        indices.push_back(base + 2); indices.push_back(base + 7); indices.push_back(base + 3);

        // Left face
        indices.push_back(base + 3); indices.push_back(base + 7); indices.push_back(base + 4);
        indices.push_back(base + 3); indices.push_back(base + 4); indices.push_back(base + 0);
    }

    // End caps
    // Start cap
    u32 startBase = static_cast<u32>(vertices.size());
    vec3 startCenter = start;
    vertices.push_back({start - right * hw - localUp * hh, -dir, color});
    vertices.push_back({start + right * hw - localUp * hh, -dir, color});
    vertices.push_back({start + right * hw + localUp * hh, -dir, color});
    vertices.push_back({start - right * hw + localUp * hh, -dir, color});
    indices.push_back(startBase + 0); indices.push_back(startBase + 2); indices.push_back(startBase + 1);
    indices.push_back(startBase + 0); indices.push_back(startBase + 3); indices.push_back(startBase + 2);

    // End cap
    u32 endBase = static_cast<u32>(vertices.size());
    vertices.push_back({end - right * hw - localUp * hh, dir, color});
    vertices.push_back({end + right * hw - localUp * hh, dir, color});
    vertices.push_back({end + right * hw + localUp * hh, dir, color});
    vertices.push_back({end - right * hw + localUp * hh, dir, color});
    indices.push_back(endBase + 0); indices.push_back(endBase + 1); indices.push_back(endBase + 2);
    indices.push_back(endBase + 0); indices.push_back(endBase + 2); indices.push_back(endBase + 3);

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createGrid(f32 size, f32 spacing, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 halfSize = size * 0.5f;
    i32 lineCount = static_cast<i32>(size / spacing) + 1;

    vec3 normal(0, 1, 0);

    // Lines along X axis
    for (i32 i = 0; i < lineCount; ++i) {
        f32 z = -halfSize + i * spacing;
        u32 baseIndex = static_cast<u32>(vertices.size());

        vertices.push_back({{-halfSize, 0, z}, normal, color});
        vertices.push_back({{halfSize, 0, z}, normal, color});

        // Create thin quad for line
        vertices.push_back({{-halfSize, 0.01f, z}, normal, color});
        vertices.push_back({{halfSize, 0.01f, z}, normal, color});

        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 3);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 3);
        indices.push_back(baseIndex + 2);
    }

    // Lines along Z axis
    for (i32 i = 0; i < lineCount; ++i) {
        f32 x = -halfSize + i * spacing;
        u32 baseIndex = static_cast<u32>(vertices.size());

        vertices.push_back({{x, 0, -halfSize}, normal, color});
        vertices.push_back({{x, 0, halfSize}, normal, color});

        vertices.push_back({{x, 0.01f, -halfSize}, normal, color});
        vertices.push_back({{x, 0.01f, halfSize}, normal, color});

        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 3);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 3);
        indices.push_back(baseIndex + 2);
    }

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createArrow(vec3 start, vec3 end, f32 headSize, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    vec3 dir = glm::normalize(end - start);
    vec3 up = vec3(0, 1, 0);
    if (std::abs(glm::dot(dir, up)) > 0.99f) {
        up = vec3(1, 0, 0);
    }

    vec3 right = glm::normalize(glm::cross(dir, up));
    vec3 localUp = glm::normalize(glm::cross(right, dir));

    f32 shaftRadius = headSize * 0.15f;
    vec3 headBase = end - dir * headSize;

    // Shaft (simplified as box)
    auto [shaftVerts, shaftIndices] = createBeam(start, headBase, shaftRadius * 2, shaftRadius * 2, color);
    vertices = shaftVerts;
    indices = shaftIndices;

    // Arrow head (cone approximation with 6 sides)
    u32 baseIndex = static_cast<u32>(vertices.size());
    u32 coneSegments = 6;

    // Tip vertex
    vertices.push_back({end, dir, color});

    // Base vertices
    for (u32 i = 0; i < coneSegments; ++i) {
        f32 angle = static_cast<f32>(i) / static_cast<f32>(coneSegments) * 2.0f * 3.14159f;
        vec3 offset = right * cos(angle) * headSize * 0.5f + localUp * sin(angle) * headSize * 0.5f;
        vec3 pos = headBase + offset;
        vec3 normal = glm::normalize(offset + dir * 0.5f);
        vertices.push_back({pos, normal, color});
    }

    // Cone faces
    for (u32 i = 0; i < coneSegments; ++i) {
        u32 next = (i + 1) % coneSegments;
        indices.push_back(baseIndex);  // Tip
        indices.push_back(baseIndex + 1 + i);
        indices.push_back(baseIndex + 1 + next);
    }

    // Base cap
    u32 centerIndex = static_cast<u32>(vertices.size());
    vertices.push_back({headBase, -dir, color});
    for (u32 i = 0; i < coneSegments; ++i) {
        u32 next = (i + 1) % coneSegments;
        indices.push_back(centerIndex);
        indices.push_back(baseIndex + 1 + next);
        indices.push_back(baseIndex + 1 + i);
    }

    return {vertices, indices};
}

void applyStressColoring(std::vector<Vertex>& vertices, f32 stress) {
    vec3 color = StressColors::fromStress(stress);
    for (auto& vertex : vertices) {
        vertex.color = color;
    }
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createDoor(vec3 position, f32 width, f32 height, f32 depth, vec3 color) {
    // Door is essentially a column with a wood/door color
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 hw = width * 0.5f;
    f32 hd = depth * 0.5f;

    vec3 corners[8] = {
        position + vec3(-hw, 0, -hd),
        position + vec3(hw, 0, -hd),
        position + vec3(hw, 0, hd),
        position + vec3(-hw, 0, hd),
        position + vec3(-hw, height, -hd),
        position + vec3(hw, height, -hd),
        position + vec3(hw, height, hd),
        position + vec3(-hw, height, hd),
    };

    auto addFace = [&](u32 i0, u32 i1, u32 i2, u32 i3, vec3 normal) {
        u32 baseIndex = static_cast<u32>(vertices.size());
        vertices.push_back({corners[i0], normal, color});
        vertices.push_back({corners[i1], normal, color});
        vertices.push_back({corners[i2], normal, color});
        vertices.push_back({corners[i3], normal, color});
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 3);
    };

    addFace(0, 1, 5, 4, vec3(0, 0, -1));
    addFace(2, 3, 7, 6, vec3(0, 0, 1));
    addFace(3, 0, 4, 7, vec3(-1, 0, 0));
    addFace(1, 2, 6, 5, vec3(1, 0, 0));
    addFace(4, 5, 6, 7, vec3(0, 1, 0));
    addFace(3, 2, 1, 0, vec3(0, -1, 0));

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createWindow(vec3 position, f32 width, f32 height, f32 depth, vec3 color) {
    // Window with glass panel (semi-transparent blue tint)
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 hw = width * 0.5f;
    f32 hd = depth * 0.5f;

    vec3 glassColor = color;

    vec3 corners[8] = {
        position + vec3(-hw, 0, -hd),
        position + vec3(hw, 0, -hd),
        position + vec3(hw, 0, hd),
        position + vec3(-hw, 0, hd),
        position + vec3(-hw, height, -hd),
        position + vec3(hw, height, -hd),
        position + vec3(hw, height, hd),
        position + vec3(-hw, height, hd),
    };

    auto addFace = [&](u32 i0, u32 i1, u32 i2, u32 i3, vec3 normal, vec3 faceColor) {
        u32 baseIndex = static_cast<u32>(vertices.size());
        vertices.push_back({corners[i0], normal, faceColor});
        vertices.push_back({corners[i1], normal, faceColor});
        vertices.push_back({corners[i2], normal, faceColor});
        vertices.push_back({corners[i3], normal, faceColor});
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 1);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 0);
        indices.push_back(baseIndex + 2);
        indices.push_back(baseIndex + 3);
    };

    addFace(0, 1, 5, 4, vec3(0, 0, -1), glassColor);
    addFace(2, 3, 7, 6, vec3(0, 0, 1), glassColor);
    addFace(3, 0, 4, 7, vec3(-1, 0, 0), glassColor);
    addFace(1, 2, 6, 5, vec3(1, 0, 0), glassColor);
    addFace(4, 5, 6, 7, vec3(0, 1, 0), glassColor);
    addFace(3, 2, 1, 0, vec3(0, -1, 0), glassColor);

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createRoof(vec3 position, f32 width, f32 depth, f32 height, f32 pitch, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    // Add overhang (eaves)
    f32 overhang = 2.0f;  // 2ft overhang
    f32 hw = (width * 0.5f) + overhang;
    f32 hd = (depth * 0.5f) + overhang;

    if (pitch <= 0.01f) {
        // Flat roof with overhang
        vec3 corners[8] = {
            position + vec3(-hw, 0, -hd),
            position + vec3(hw, 0, -hd),
            position + vec3(hw, 0, hd),
            position + vec3(-hw, 0, hd),
            position + vec3(-hw, height, -hd),
            position + vec3(hw, height, -hd),
            position + vec3(hw, height, hd),
            position + vec3(-hw, height, hd),
        };

        auto addFace = [&](u32 i0, u32 i1, u32 i2, u32 i3, vec3 normal) {
            u32 baseIndex = static_cast<u32>(vertices.size());
            vertices.push_back({corners[i0], normal, color});
            vertices.push_back({corners[i1], normal, color});
            vertices.push_back({corners[i2], normal, color});
            vertices.push_back({corners[i3], normal, color});
            indices.push_back(baseIndex + 0);
            indices.push_back(baseIndex + 1);
            indices.push_back(baseIndex + 2);
            indices.push_back(baseIndex + 0);
            indices.push_back(baseIndex + 2);
            indices.push_back(baseIndex + 3);
        };

        addFace(0, 1, 5, 4, vec3(0, 0, -1));
        addFace(2, 3, 7, 6, vec3(0, 0, 1));
        addFace(3, 0, 4, 7, vec3(-1, 0, 0));
        addFace(1, 2, 6, 5, vec3(1, 0, 0));
        addFace(4, 5, 6, 7, vec3(0, 1, 0));
        addFace(3, 2, 1, 0, vec3(0, -1, 0));
    } else {
        // Hip roof (4 sloped sides) with overhang
        f32 ridgeHeight = height + pitch * std::min(hw, hd);

        // Base corners (at eaves level, with overhang)
        vec3 p0 = position + vec3(-hw, 0, -hd);  // back-left
        vec3 p1 = position + vec3(hw, 0, -hd);   // back-right
        vec3 p2 = position + vec3(hw, 0, hd);    // front-right
        vec3 p3 = position + vec3(-hw, 0, hd);   // front-left

        // Ridge line (shorter than base, centered)
        f32 ridgeLen = std::max(0.0f, (width - depth) * 0.5f);
        vec3 r0 = position + vec3(-ridgeLen, ridgeHeight, 0);  // ridge left
        vec3 r1 = position + vec3(ridgeLen, ridgeHeight, 0);   // ridge right

        // If building is roughly square, ridge becomes a point (pyramid)
        if (ridgeLen < 1.0f) {
            // Pyramid roof (4 triangular faces meeting at apex)
            vec3 apex = position + vec3(0, ridgeHeight, 0);

            // Front slope
            vec3 frontNormal = glm::normalize(glm::cross(p2 - p3, apex - p3));
            u32 base = static_cast<u32>(vertices.size());
            vertices.push_back({p3, frontNormal, color});
            vertices.push_back({p2, frontNormal, color});
            vertices.push_back({apex, frontNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);

            // Right slope
            vec3 rightNormal = glm::normalize(glm::cross(p1 - p2, apex - p2));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p2, rightNormal, color});
            vertices.push_back({p1, rightNormal, color});
            vertices.push_back({apex, rightNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);

            // Back slope
            vec3 backNormal = glm::normalize(glm::cross(p0 - p1, apex - p1));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p1, backNormal, color});
            vertices.push_back({p0, backNormal, color});
            vertices.push_back({apex, backNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);

            // Left slope
            vec3 leftNormal = glm::normalize(glm::cross(p3 - p0, apex - p0));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p0, leftNormal, color});
            vertices.push_back({p3, leftNormal, color});
            vertices.push_back({apex, leftNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
        } else {
            // Hip roof with ridge line
            // Front slope (trapezoid)
            vec3 frontNormal = glm::normalize(glm::cross(p2 - p3, r0 - p3));
            u32 base = static_cast<u32>(vertices.size());
            vertices.push_back({p3, frontNormal, color});
            vertices.push_back({p2, frontNormal, color});
            vertices.push_back({r1, frontNormal, color});
            vertices.push_back({r0, frontNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
            indices.push_back(base + 0); indices.push_back(base + 2); indices.push_back(base + 3);

            // Back slope (trapezoid)
            vec3 backNormal = glm::normalize(glm::cross(p0 - p1, r1 - p1));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p1, backNormal, color});
            vertices.push_back({p0, backNormal, color});
            vertices.push_back({r0, backNormal, color});
            vertices.push_back({r1, backNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
            indices.push_back(base + 0); indices.push_back(base + 2); indices.push_back(base + 3);

            // Right hip (triangle)
            vec3 rightNormal = glm::normalize(glm::cross(p1 - p2, r1 - p2));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p2, rightNormal, color});
            vertices.push_back({p1, rightNormal, color});
            vertices.push_back({r1, rightNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);

            // Left hip (triangle)
            vec3 leftNormal = glm::normalize(glm::cross(p3 - p0, r0 - p0));
            base = static_cast<u32>(vertices.size());
            vertices.push_back({p0, leftNormal, color});
            vertices.push_back({p3, leftNormal, color});
            vertices.push_back({r0, leftNormal, color});
            indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
        }
    }

    return {vertices, indices};
}


std::pair<std::vector<Vertex>, std::vector<u32>>
createGableRoof(vec3 position, f32 width, f32 depth, f32 wallHeight, f32 pitch,
                f32 overhang, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 hw = (width * 0.5f) + overhang;
    f32 hd = (depth * 0.5f) + overhang;
    f32 ridgeHeight = wallHeight + pitch * (width * 0.5f);

    vec3 p0 = position + vec3(-hw, wallHeight, -hd);
    vec3 p1 = position + vec3(hw, wallHeight, -hd);
    vec3 p2 = position + vec3(hw, wallHeight, hd);
    vec3 p3 = position + vec3(-hw, wallHeight, hd);
    vec3 r0 = position + vec3(0, ridgeHeight, -hd);
    vec3 r1 = position + vec3(0, ridgeHeight, hd);

    vec3 leftNormal = glm::normalize(glm::cross(p3 - p0, r0 - p0));
    u32 base = static_cast<u32>(vertices.size());
    vertices.push_back({p0, leftNormal, color});
    vertices.push_back({p3, leftNormal, color});
    vertices.push_back({r1, leftNormal, color});
    vertices.push_back({r0, leftNormal, color});
    indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
    indices.push_back(base + 0); indices.push_back(base + 2); indices.push_back(base + 3);

    vec3 rightNormal = glm::normalize(glm::cross(r0 - p1, p2 - p1));
    base = static_cast<u32>(vertices.size());
    vertices.push_back({p1, rightNormal, color});
    vertices.push_back({r0, rightNormal, color});
    vertices.push_back({r1, rightNormal, color});
    vertices.push_back({p2, rightNormal, color});
    indices.push_back(base + 0); indices.push_back(base + 1); indices.push_back(base + 2);
    indices.push_back(base + 0); indices.push_back(base + 2); indices.push_back(base + 3);

    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
createGableWall(vec3 position, f32 width, f32 wallHeight, f32 gableHeight, f32 thickness,
                vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;

    f32 hw = width * 0.5f;
    f32 ht = thickness * 0.5f;

    vec3 p0 = position + vec3(-hw, 0, 0);
    vec3 p1 = position + vec3(hw, 0, 0);
    vec3 p2 = position + vec3(hw, wallHeight, 0);
    vec3 p3 = position + vec3(0, wallHeight + gableHeight, 0);
    vec3 p4 = position + vec3(-hw, wallHeight, 0);

    // Front pentagon
    u32 base = static_cast<u32>(vertices.size());
    vertices.push_back({p0 + vec3(0,0,ht), vec3(0,0,1), color});
    vertices.push_back({p1 + vec3(0,0,ht), vec3(0,0,1), color});
    vertices.push_back({p2 + vec3(0,0,ht), vec3(0,0,1), color});
    vertices.push_back({p3 + vec3(0,0,ht), vec3(0,0,1), color});
    vertices.push_back({p4 + vec3(0,0,ht), vec3(0,0,1), color});
    indices.push_back(base+0); indices.push_back(base+1); indices.push_back(base+2);
    indices.push_back(base+0); indices.push_back(base+2); indices.push_back(base+3);
    indices.push_back(base+0); indices.push_back(base+3); indices.push_back(base+4);

    // Back pentagon
    base = static_cast<u32>(vertices.size());
    vertices.push_back({p0 + vec3(0,0,-ht), vec3(0,0,-1), color});
    vertices.push_back({p4 + vec3(0,0,-ht), vec3(0,0,-1), color});
    vertices.push_back({p3 + vec3(0,0,-ht), vec3(0,0,-1), color});
    vertices.push_back({p2 + vec3(0,0,-ht), vec3(0,0,-1), color});
    vertices.push_back({p1 + vec3(0,0,-ht), vec3(0,0,-1), color});
    indices.push_back(base+0); indices.push_back(base+1); indices.push_back(base+2);
    indices.push_back(base+0); indices.push_back(base+2); indices.push_back(base+3);
    indices.push_back(base+0); indices.push_back(base+3); indices.push_back(base+4);

    return {vertices, indices};
}

namespace CSG {

std::pair<std::vector<Vertex>, std::vector<u32>>
meshUnion(const std::pair<std::vector<Vertex>, std::vector<u32>>& a,
          const std::pair<std::vector<Vertex>, std::vector<u32>>& b) {
    std::vector<Vertex> vertices = a.first;
    std::vector<u32> indices = a.second;
    u32 offset = static_cast<u32>(vertices.size());
    vertices.insert(vertices.end(), b.first.begin(), b.first.end());
    for (u32 idx : b.second) {
        indices.push_back(idx + offset);
    }
    return {vertices, indices};
}

std::pair<std::vector<Vertex>, std::vector<u32>>
wallWithOpening(vec3 wallStart, vec3 wallEnd, f32 wallHeight, f32 thickness,
                vec3 openingPos, f32 openingWidth, f32 openingHeight, vec3 color) {
    std::vector<Vertex> vertices;
    std::vector<u32> indices;
    f32 wallLength = glm::length(wallEnd - wallStart);
    f32 openLeft = openingPos.x;
    f32 openRight = openLeft + openingWidth;
    f32 openBottom = openingPos.y;
    f32 openTop = openBottom + openingHeight;

    if (openBottom > 0) {
        auto strip = createColumn(wallStart, wallLength, thickness, openBottom, color);
        auto result = meshUnion({vertices, indices}, strip);
        vertices = result.first; indices = result.second;
    }
    if (openTop < wallHeight) {
        vec3 topStart = wallStart + vec3(0, openTop, 0);
        auto strip = createColumn(topStart, wallLength, thickness, wallHeight - openTop, color);
        auto result = meshUnion({vertices, indices}, strip);
        vertices = result.first; indices = result.second;
    }
    return {vertices, indices};
}

} // namespace CSG

} // namespace Geometry
} // namespace arch
