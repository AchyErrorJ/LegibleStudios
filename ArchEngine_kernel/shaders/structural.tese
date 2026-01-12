#version 450

// Tessellation Evaluation Shader for displacement mapping
// Samples height map and displaces vertices along normals

layout(triangles, equal_spacing, ccw) in;

// Inputs from tessellation control shader
layout(location = 0) in vec3 inWorldPos[];
layout(location = 1) in vec3 inNormal[];
layout(location = 2) in vec2 inTexCoord[];
layout(location = 3) in flat int inMaterialIndex[];
layout(location = 4) in vec4 inVertexColor[];

// Outputs to fragment shader
layout(location = 0) out vec3 outWorldPos;
layout(location = 1) out vec3 outNormal;
layout(location = 2) out vec2 outTexCoord;
layout(location = 3) out flat int outMaterialIndex;
layout(location = 4) out vec4 outVertexColor;

// Uniform buffer
layout(set = 0, binding = 0) uniform UniformBuffer {
    mat4 view;
    mat4 proj;
    vec4 lightDir;
    vec4 cameraPos;
    vec4 clipPlane;
    vec4 sectionPlane;
    float exposure;
    float shadowStrength;
    float ssaoStrength;
    int vizMode;
    vec4 materialParams;
    vec4 bloomParams;
    int tonemapMode;
    float tessellationLevel;
    float displacementScale;
    float padding1;
} ubo;

// Height map sampler (set 1, binding 5 - after other material textures)
layout(set = 1, binding = 5) uniform sampler2D heightMap;

// Interpolate attribute using barycentric coordinates
vec3 interpolate3(vec3 v0, vec3 v1, vec3 v2) {
    return gl_TessCoord.x * v0 + gl_TessCoord.y * v1 + gl_TessCoord.z * v2;
}

vec2 interpolate2(vec2 v0, vec2 v1, vec2 v2) {
    return gl_TessCoord.x * v0 + gl_TessCoord.y * v1 + gl_TessCoord.z * v2;
}

vec4 interpolate4(vec4 v0, vec4 v1, vec4 v2) {
    return gl_TessCoord.x * v0 + gl_TessCoord.y * v1 + gl_TessCoord.z * v2;
}

void main() {
    // Interpolate vertex attributes using barycentric coordinates
    vec3 worldPos = interpolate3(inWorldPos[0], inWorldPos[1], inWorldPos[2]);
    vec3 normal = normalize(interpolate3(inNormal[0], inNormal[1], inNormal[2]));
    vec2 texCoord = interpolate2(inTexCoord[0], inTexCoord[1], inTexCoord[2]);
    vec4 vertexColor = interpolate4(inVertexColor[0], inVertexColor[1], inVertexColor[2]);

    // Use material index from first vertex (flat interpolation)
    int materialIndex = inMaterialIndex[0];

    // Sample height map
    float height = texture(heightMap, texCoord).r;

    // Normalize height from 0-1 to -0.5 to 0.5 for centered displacement
    height = height - 0.5;

    // Apply displacement along normal
    float displacement = height * ubo.displacementScale;
    worldPos += normal * displacement;

    // Recompute normal using finite differences (optional, for better lighting)
    // This is a simplified approach - for better results, sample neighbors
    float texelSize = 1.0 / 1024.0; // Assume 1024x1024 height map
    float heightL = texture(heightMap, texCoord + vec2(-texelSize, 0)).r;
    float heightR = texture(heightMap, texCoord + vec2(texelSize, 0)).r;
    float heightD = texture(heightMap, texCoord + vec2(0, -texelSize)).r;
    float heightU = texture(heightMap, texCoord + vec2(0, texelSize)).r;

    // Compute tangent-space normal from height differences
    vec3 tangent = vec3(1, 0, 0);
    vec3 bitangent = vec3(0, 1, 0);

    // Approximate the displaced normal
    float dX = (heightR - heightL) * ubo.displacementScale;
    float dY = (heightU - heightD) * ubo.displacementScale;
    vec3 displacedNormal = normalize(normal + tangent * (-dX * 0.5) + bitangent * (-dY * 0.5));

    // Output
    outWorldPos = worldPos;
    outNormal = displacedNormal;
    outTexCoord = texCoord;
    outMaterialIndex = materialIndex;
    outVertexColor = vertexColor;

    // Transform to clip space
    gl_Position = ubo.proj * ubo.view * vec4(worldPos, 1.0);
}
