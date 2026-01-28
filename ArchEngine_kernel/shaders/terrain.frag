#version 450

// Inputs from vertex shader
layout(location = 0) in vec3 fragPosition;
layout(location = 1) in vec3 fragNormal;
layout(location = 2) in float fragElevation;

// Output
layout(location = 0) out vec4 outColor;

// Push constants for elevation range
layout(push_constant) uniform TerrainConstants {
    float minElevation;
    float maxElevation;
    float elevationRange;
    float padding;
} terrain;

// Topographic color ramp (low to high elevation)
const vec3 COLOR_DEEP = vec3(0.1, 0.3, 0.5);    // Deep blue/green
const vec3 COLOR_LOW = vec3(0.2, 0.5, 0.3);     // Green
const vec3 COLOR_MID = vec3(0.6, 0.5, 0.3);     // Tan/brown
const vec3 COLOR_HIGH = vec3(0.7, 0.7, 0.7);    // Gray
const vec3 COLOR_PEAK = vec3(1.0, 1.0, 1.0);    // White

vec3 getElevationColor(float t) {
    // Smooth gradient between colors
    if (t < 0.25) {
        return mix(COLOR_DEEP, COLOR_LOW, t * 4.0);
    } else if (t < 0.5) {
        return mix(COLOR_LOW, COLOR_MID, (t - 0.25) * 4.0);
    } else if (t < 0.75) {
        return mix(COLOR_MID, COLOR_HIGH, (t - 0.5) * 4.0);
    } else {
        return mix(COLOR_HIGH, COLOR_PEAK, (t - 0.75) * 4.0);
    }
}

void main() {
    // DEBUG: Make terrain BRIGHT RED to ensure visibility
    outColor = vec4(1.0, 0.0, 0.0, 1.0);

    // Base color from elevation
    vec3 baseColor = getElevationColor(fragElevation);

    // Simple directional lighting
    vec3 lightDir = normalize(vec3(1.0, 1.0, 0.5));
    float diffuse = max(dot(normalize(fragNormal), lightDir), 0.0);
    float ambient = 0.3;

    vec3 finalColor = baseColor * (diffuse + ambient);

    // Add subtle contour lines
    float contour = step(0.95, fract(fragElevation * 20.0));
    finalColor = mix(finalColor, vec3(0.4, 0.3, 0.2), contour * 0.3);

    //outColor = vec4(finalColor, 1.0);  // DISABLED FOR DEBUG
}
