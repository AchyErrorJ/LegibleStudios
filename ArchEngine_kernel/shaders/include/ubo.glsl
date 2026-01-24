// Shared Uniform Buffer Object definition
// This file is included by all shaders to ensure UBO layout consistency
// MUST match C++ struct UniformBufferObject in types.hpp exactly

#ifndef UBO_GLSL
#define UBO_GLSL

// Maximum number of lights (must match C++ MAX_LIGHTS)
const uint MAX_LIGHTS = 16u;

// Light type constants
const uint LIGHT_TYPE_DIRECTIONAL = 0u;
const uint LIGHT_TYPE_POINT = 1u;
const uint LIGHT_TYPE_SPOT = 2u;

// GPU-friendly light structure (must match C++ GPULight)
struct GPULight {
    vec4 positionType;      // xyz = world position, w = type
    vec4 directionRange;    // xyz = direction, w = range
    vec4 colorIntensity;    // rgb = color, a = intensity
    vec4 spotParams;        // x = innerAngle (cos), y = outerAngle (cos), z = shadowIndex, w = reserved
};

layout(set = 0, binding = 0) uniform UniformBufferObject {
    mat4 view;
    mat4 proj;
    mat4 lightViewProj;         // Shadow mapping light space transform
    vec4 lightDirection;        // Directional light direction (sun), xyz = direction, w unused
    vec4 clipPlane;             // Section clipping plane (xyz = normal, w = distance)
    float time;                 // Animation time
    float shadowBias;           // Shadow mapping bias
    uint enableClipping;        // Section clipping enabled flag
    uint enableShadows;         // Shadow mapping enabled flag
    uint outputLinearHDR;       // Output linear HDR (skip tonemapping in shader)
    float exposure;             // Exposure multiplier for tonemapping
    float tessellationLevel;    // Tessellation subdivision level (1-64)
    float displacementScale;    // Height map displacement scale
    vec4 materialParams;        // x = UV scale, y = normal strength, z = brightness, w = contrast
    vec4 materialParams2;       // x = saturation, y = roughnessOffset, z = metallicOffset, w = aoStrength
    vec4 materialTint;          // RGB tint multiplier, w = unused
    vec4 pomParams;             // x = enabled (0/1), y = heightScale, z = minLayers, w = maxLayers
    // Debug visualization
    uint materialDebugMode;     // 0=None, 1=Displacement, 2=POMDepth, 3=Normals, 4=UVs, 5=AO
    // Per-element material overrides
    uint overrideMask;          // Bitfield for which element overrides are active
    float _pad1, _pad2;         // Padding to maintain 16-byte alignment
    vec4 elementOverride1;      // x = uvScale, y = normalStrength, z = brightness, w = contrast
    vec4 elementOverride2;      // x = saturation, y = roughness, z = metallic, w = aoStrength
    vec4 elementOverride3;      // RGB = tint, w = uvRotation (radians)
    // Multiple light sources
    uint numLights;             // Number of active lights (0-16)
    float _pad3, _pad4, _pad5;  // Padding for alignment
    GPULight lights[MAX_LIGHTS];  // Array of lights
} ubo;

// Material override mask bits (must match C++ MaterialOverrideBits)
const uint OVERRIDE_UV_SCALE        = (1u << 0);
const uint OVERRIDE_UV_ROTATION     = (1u << 1);
const uint OVERRIDE_NORMAL_STRENGTH = (1u << 2);
const uint OVERRIDE_BRIGHTNESS      = (1u << 3);
const uint OVERRIDE_CONTRAST        = (1u << 4);
const uint OVERRIDE_SATURATION      = (1u << 5);
const uint OVERRIDE_ROUGHNESS       = (1u << 6);
const uint OVERRIDE_METALLIC        = (1u << 7);
const uint OVERRIDE_AO_STRENGTH     = (1u << 8);
const uint OVERRIDE_TINT            = (1u << 9);

#endif // UBO_GLSL
