#version 450

// Vertex attributes
layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inColor;

// Uniform buffer
layout(set = 0, binding = 0) uniform UniformBufferObject {
    mat4 view;
    mat4 proj;
    float time;
    float padding[3];
} ubo;

// Push constants
layout(push_constant) uniform PushConstants {
    mat4 model;
    vec4 color;
} push;

// Output to fragment shader
layout(location = 0) out vec3 fragColor;
layout(location = 1) out vec3 fragNormal;
layout(location = 2) out vec3 fragPosition;
layout(location = 3) out float fragStress;

void main() {
    // Transform position
    vec4 worldPos = push.model * vec4(inPosition, 1.0);
    gl_Position = ubo.proj * ubo.view * worldPos;

    // Transform normal to world space
    mat3 normalMatrix = transpose(inverse(mat3(push.model)));
    fragNormal = normalize(normalMatrix * inNormal);

    // Pass through data
    fragPosition = worldPos.xyz;
    fragColor = inColor;

    // Extract stress from push constant color (stored in alpha or as utilization)
    fragStress = push.color.a;

    // Override color with push constant if it's not default white
    if (push.color.r > 0.01 || push.color.g > 0.01 || push.color.b > 0.01) {
        fragColor = push.color.rgb;
    }
}
