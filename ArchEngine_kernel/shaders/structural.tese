#version 450

// Tessellation Evaluation Shader for displacement mapping
// Samples height map and displaces vertices along normals

layout(triangles, equal_spacing, ccw) in;

// Inputs from tessellation control shader (must match TCS outputs)
layout(location = 0) in vec3 inFragColor[];
layout(location = 1) in vec3 inFragNormal[];
layout(location = 2) in vec3 inFragPosition[];
layout(location = 3) in float inFragStress[];
layout(location = 4) in vec4 inFragLightSpacePos[];
layout(location = 5) in vec4 inFragMaterial[];
layout(location = 6) in vec2 inFragTexCoord[];

// Outputs to fragment shader (same as vertex shader outputs)
layout(location = 0) out vec3 fragColor;
layout(location = 1) out vec3 fragNormal;
layout(location = 2) out vec3 fragPosition;
layout(location = 3) out float fragStress;
layout(location = 4) out vec4 fragLightSpacePos;
layout(location = 5) out vec4 fragMaterial;
layout(location = 6) out vec2 fragTexCoord;

// Shared UBO definition (includes override mask constants)
#include "include/ubo.glsl"

// Push constants (per-draw data including element overrides)
layout(push_constant) uniform PushConstants {
    mat4 model;
    vec4 color;
    vec4 material;       // x = metallic, y = roughness, z = ao, w = emission
    uint overrideMask;   // Which overrides are active
    float _pad1, _pad2, _pad3;  // Padding for vec4 alignment
    vec4 overrides1;     // x=uvScale, y=normalStrength, z=brightness, w=contrast
    vec4 overrides2;     // x=saturation, y=roughness, z=metallic, w=aoStrength
    vec4 overrides3;     // rgb=tint, w=uvRotation (radians)
} push;

// Height map sampler (set 1, binding 7 - after other material textures)
layout(set = 1, binding = 7) uniform sampler2D heightMap;

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

float interpolate1(float v0, float v1, float v2) {
    return gl_TessCoord.x * v0 + gl_TessCoord.y * v1 + gl_TessCoord.z * v2;
}

void main() {
    // Interpolate vertex attributes using barycentric coordinates
    vec3 position = interpolate3(inFragPosition[0], inFragPosition[1], inFragPosition[2]);
    vec3 normal = normalize(interpolate3(inFragNormal[0], inFragNormal[1], inFragNormal[2]));
    vec3 color = interpolate3(inFragColor[0], inFragColor[1], inFragColor[2]);
    vec2 texCoord = interpolate2(inFragTexCoord[0], inFragTexCoord[1], inFragTexCoord[2]);
    float stress = interpolate1(inFragStress[0], inFragStress[1], inFragStress[2]);
    vec4 lightSpacePos = interpolate4(inFragLightSpacePos[0], inFragLightSpacePos[1], inFragLightSpacePos[2]);
    vec4 material = interpolate4(inFragMaterial[0], inFragMaterial[1], inFragMaterial[2]);

    // Apply UV scale with override support (replacement, not additive)
    float uvScale = ubo.materialParams.x;
    float uvRotation = 0.0;
    if ((push.overrideMask & OVERRIDE_UV_SCALE) != 0u) {
        uvScale = push.overrides1.x;  // Use push constant override
    }
    if ((push.overrideMask & OVERRIDE_UV_ROTATION) != 0u) {
        uvRotation = push.overrides3.w;  // Rotation in radians
    }
    vec2 scaledTexCoord = texCoord * uvScale;

    // Apply rotation around center if rotation is set
    if (uvRotation != 0.0) {
        vec2 center = vec2(0.5) * uvScale;
        float cosR = cos(uvRotation);
        float sinR = sin(uvRotation);
        vec2 offset = scaledTexCoord - center;
        scaledTexCoord = vec2(
            offset.x * cosR - offset.y * sinR,
            offset.x * sinR + offset.y * cosR
        ) + center;
    }

    // Sample height map (only if displacement is enabled)
    if (ubo.displacementScale > 0.0) {
        float height = texture(heightMap, scaledTexCoord).r;

        // Normalize height from 0-1 to -0.5 to 0.5 for centered displacement
        height = height - 0.5;

        // Apply displacement along normal
        float displacement = height * ubo.displacementScale;
        position += normal * displacement;

        // Recompute normal using finite differences for better lighting
        // Scale texel size with UV scale so gradients sample correctly when texture is tiled
        float baseTexelSize = 1.0 / 1024.0; // Assume 1024x1024 height map
        float texelSize = baseTexelSize * uvScale;
        float heightL = texture(heightMap, scaledTexCoord + vec2(-texelSize, 0)).r;
        float heightR = texture(heightMap, scaledTexCoord + vec2(texelSize, 0)).r;
        float heightD = texture(heightMap, scaledTexCoord + vec2(0, -texelSize)).r;
        float heightU = texture(heightMap, scaledTexCoord + vec2(0, texelSize)).r;

        // Compute displaced normal from height gradients
        float dX = (heightR - heightL) * ubo.displacementScale * 2.0;
        float dY = (heightU - heightD) * ubo.displacementScale * 2.0;

        // Build tangent space (simplified - assumes Y-up world)
        vec3 tangent = normalize(cross(vec3(0, 1, 0), normal));
        if (length(tangent) < 0.001) {
            tangent = normalize(cross(vec3(1, 0, 0), normal));
        }
        vec3 bitangent = normalize(cross(normal, tangent));

        // Perturb normal based on height gradients
        normal = normalize(normal - tangent * dX - bitangent * dY);

        // Recalculate light space position after displacement
        lightSpacePos = ubo.lightViewProj * vec4(position, 1.0);
    }

    // Output interpolated/displaced attributes
    fragPosition = position;
    fragNormal = normal;
    fragColor = color;
    // Pass the original texCoord - fragment shader handles UV scaling
    // This ensures displacement and texture sampling use consistent coordinates
    fragTexCoord = texCoord;
    fragStress = stress;
    fragLightSpacePos = lightSpacePos;
    fragMaterial = material;

    // Transform to clip space
    gl_Position = ubo.proj * ubo.view * vec4(position, 1.0);

    // Clip distance for section clipping
    if (ubo.enableClipping != 0u) {
        gl_ClipDistance[0] = dot(vec4(position, 1.0), ubo.clipPlane);
    } else {
        gl_ClipDistance[0] = 1.0;
    }
}
