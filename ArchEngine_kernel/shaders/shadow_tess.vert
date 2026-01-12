#version 450

// Vertex shader for tessellated shadow pass
// Passes vertex data to tessellation control shader

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inColor;      // Unused
layout(location = 3) in vec2 inTexCoord;
layout(location = 4) in float inStress;    // Unused

// Output to tessellation control shader
layout(location = 0) out vec3 outPosition;
layout(location = 1) out vec3 outNormal;
layout(location = 2) out vec2 outTexCoord;

void main() {
    outPosition = inPosition;
    outNormal = inNormal;
    outTexCoord = inTexCoord;
}
