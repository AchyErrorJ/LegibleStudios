#version 450

// Input from vertex shader
layout(location = 0) in vec3 fragColor;
layout(location = 1) in vec3 fragNormal;
layout(location = 2) in vec3 fragPosition;
layout(location = 3) in float fragStress;

// Output
layout(location = 0) out vec4 outColor;

// Stress color constants (matching types.hpp)
const vec3 STRESS_SAFE     = vec3(0.133, 0.773, 0.369);  // Green
const vec3 STRESS_WARNING  = vec3(0.918, 0.702, 0.031);  // Yellow
const vec3 STRESS_CRITICAL = vec3(0.976, 0.451, 0.086);  // Orange
const vec3 STRESS_FAILURE  = vec3(0.937, 0.267, 0.267);  // Red

// Light direction (sun-like, from top-right-front)
const vec3 lightDir = normalize(vec3(0.5, 1.0, 0.3));
const vec3 lightColor = vec3(1.0, 0.98, 0.95);
const float ambientStrength = 0.3;
const float specularStrength = 0.4;

// Calculate stress color based on utilization ratio
vec3 getStressColor(float stress) {
    if (stress < 0.7) {
        return STRESS_SAFE;
    } else if (stress < 0.9) {
        float t = (stress - 0.7) / 0.2;
        return mix(STRESS_SAFE, STRESS_WARNING, t);
    } else if (stress < 1.0) {
        float t = (stress - 0.9) / 0.1;
        return mix(STRESS_WARNING, STRESS_CRITICAL, t);
    } else {
        float t = min((stress - 1.0) / 0.5, 1.0);
        return mix(STRESS_CRITICAL, STRESS_FAILURE, t);
    }
}

void main() {
    // Normalize interpolated normal
    vec3 normal = normalize(fragNormal);

    // Basic Phong lighting
    // Ambient
    vec3 ambient = ambientStrength * lightColor;

    // Diffuse
    float diff = max(dot(normal, lightDir), 0.0);
    vec3 diffuse = diff * lightColor;

    // Simple specular (view-independent for simplicity)
    vec3 reflectDir = reflect(-lightDir, normal);
    vec3 viewDir = normalize(-fragPosition);  // Approximate
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32.0);
    vec3 specular = specularStrength * spec * lightColor;

    // Combine lighting
    vec3 lighting = ambient + diffuse + specular;

    // Use stress coloring if stress is significant, otherwise use vertex color
    vec3 baseColor = fragColor;
    if (fragStress > 0.01) {
        baseColor = getStressColor(fragStress);
    }

    // Final color
    vec3 result = lighting * baseColor;

    // Apply slight tone mapping for better visuals
    result = result / (result + vec3(1.0));

    // Gamma correction
    result = pow(result, vec3(1.0 / 2.2));

    outColor = vec4(result, 1.0);
}
