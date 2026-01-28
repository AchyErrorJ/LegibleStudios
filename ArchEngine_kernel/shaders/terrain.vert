#version 450

// Vertex attributes
layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inColor;
layout(location = 3) in vec2 inTexCoord;
layout(location = 4) in float inStress;

// Camera uniform buffer
layout(binding = 0) uniform CameraBuffer {
    mat4 view;
    mat4 proj;
    mat4 viewProj;
} camera;

// Push constants for elevation range
layout(push_constant) uniform TerrainConstants {
    float minElevation;
    float maxElevation;
    float elevationRange;
    float padding;
} terrain;

// Outputs to fragment shader
layout(location = 0) out vec3 fragPosition;
layout(location = 1) out vec3 fragNormal;
layout(location = 2) out float fragElevation;  // Normalized 0-1

void main() {
    vec4 worldPos = vec4(inPosition, 1.0);
    gl_Position = camera.viewProj * worldPos;

    fragPosition = worldPos.xyz;
    fragNormal = inNormal;

    // Normalize elevation to 0-1 for coloring
    // Position is already in feet (scaled by C++ code)
    float elevationFeet = inPosition.y;
    fragElevation = (elevationFeet - terrain.minElevation) / max(terrain.elevationRange, 0.001);
}
