#version 450

// Tessellation Control Shader for displacement mapping
// Controls tessellation level based on distance and screen-space edge length

layout(vertices = 3) out;

// Inputs from vertex shader
layout(location = 0) in vec3 inWorldPos[];
layout(location = 1) in vec3 inNormal[];
layout(location = 2) in vec2 inTexCoord[];
layout(location = 3) in flat int inMaterialIndex[];
layout(location = 4) in vec4 inVertexColor[];

// Outputs to tessellation evaluation shader
layout(location = 0) out vec3 outWorldPos[];
layout(location = 1) out vec3 outNormal[];
layout(location = 2) out vec2 outTexCoord[];
layout(location = 3) out flat int outMaterialIndex[];
layout(location = 4) out vec4 outVertexColor[];

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

// Compute tessellation level based on edge length in screen space
float screenSpaceEdgeLength(vec3 p0, vec3 p1) {
    vec4 clip0 = ubo.proj * ubo.view * vec4(p0, 1.0);
    vec4 clip1 = ubo.proj * ubo.view * vec4(p1, 1.0);

    vec2 screen0 = clip0.xy / clip0.w;
    vec2 screen1 = clip1.xy / clip1.w;

    return length(screen1 - screen0) * 1000.0; // Scale factor for reasonable tessellation
}

// Compute tessellation level based on distance from camera
float distanceBasedTessLevel(vec3 worldPos) {
    float dist = length(worldPos - ubo.cameraPos.xyz);

    // Tessellation falls off with distance
    // Close: high tessellation, Far: low tessellation
    float maxDist = 50.0;
    float minDist = 2.0;
    float t = clamp((dist - minDist) / (maxDist - minDist), 0.0, 1.0);

    // Interpolate between max and min tessellation levels
    float maxTess = ubo.tessellationLevel;
    float minTess = 1.0;

    return mix(maxTess, minTess, t * t); // Quadratic falloff
}

void main() {
    // Pass through vertex attributes
    outWorldPos[gl_InvocationID] = inWorldPos[gl_InvocationID];
    outNormal[gl_InvocationID] = inNormal[gl_InvocationID];
    outTexCoord[gl_InvocationID] = inTexCoord[gl_InvocationID];
    outMaterialIndex[gl_InvocationID] = inMaterialIndex[gl_InvocationID];
    outVertexColor[gl_InvocationID] = inVertexColor[gl_InvocationID];

    // Only first invocation sets tessellation levels
    if (gl_InvocationID == 0) {
        // Compute center of triangle for distance-based tessellation
        vec3 center = (inWorldPos[0] + inWorldPos[1] + inWorldPos[2]) / 3.0;
        float distTess = distanceBasedTessLevel(center);

        // Optionally use screen-space edge length for adaptive tessellation
        float edge0 = screenSpaceEdgeLength(inWorldPos[1], inWorldPos[2]);
        float edge1 = screenSpaceEdgeLength(inWorldPos[2], inWorldPos[0]);
        float edge2 = screenSpaceEdgeLength(inWorldPos[0], inWorldPos[1]);

        // Combine distance and edge-based tessellation
        float tess0 = clamp(min(distTess, edge0), 1.0, 64.0);
        float tess1 = clamp(min(distTess, edge1), 1.0, 64.0);
        float tess2 = clamp(min(distTess, edge2), 1.0, 64.0);

        // Set outer tessellation levels (one per edge)
        gl_TessLevelOuter[0] = tess0;
        gl_TessLevelOuter[1] = tess1;
        gl_TessLevelOuter[2] = tess2;

        // Set inner tessellation level (average of outer levels)
        gl_TessLevelInner[0] = (tess0 + tess1 + tess2) / 3.0;
    }
}
