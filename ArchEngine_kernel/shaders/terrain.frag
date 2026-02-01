#version 450

// Inputs from vertex shader
layout(location = 0) in vec3 fragPosition;
layout(location = 1) in vec3 fragNormal;
layout(location = 2) in float fragElevation;
layout(location = 3) in vec2 fragUV;

// Output
layout(location = 0) out vec4 outColor;

// Push constants for elevation range
layout(push_constant) uniform TerrainConstants {
    float minElevation;
    float maxElevation;
    float elevationRange;
    float padding;
} terrain;

// Procedural noise functions for texture detail
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);  // Smooth interpolation

    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// Topographic color ramp - earthy natural tones
const vec3 COLOR_GRASS = vec3(0.22, 0.38, 0.18);   // Dark grass
const vec3 COLOR_MEADOW = vec3(0.35, 0.50, 0.22);  // Light grass
const vec3 COLOR_DIRT = vec3(0.45, 0.35, 0.22);    // Dirt/earth
const vec3 COLOR_ROCK = vec3(0.40, 0.38, 0.35);    // Gray rock
const vec3 COLOR_STONE = vec3(0.55, 0.52, 0.48);   // Light stone

vec3 getElevationColor(float t, float noiseVal) {
    // Mix colors based on elevation with noise variation
    vec3 color;
    if (t < 0.3) {
        color = mix(COLOR_GRASS, COLOR_MEADOW, t / 0.3);
    } else if (t < 0.6) {
        color = mix(COLOR_MEADOW, COLOR_DIRT, (t - 0.3) / 0.3);
    } else if (t < 0.85) {
        color = mix(COLOR_DIRT, COLOR_ROCK, (t - 0.6) / 0.25);
    } else {
        color = mix(COLOR_ROCK, COLOR_STONE, (t - 0.85) / 0.15);
    }

    // Add noise-based color variation
    color *= 0.85 + noiseVal * 0.3;

    return color;
}

void main() {
    // World-space UV for consistent texture scale (1 unit = ~1 foot)
    vec2 worldUV = fragPosition.xz * 0.02;  // Scale for detail

    // Multi-octave noise for natural variation
    float largeNoise = fbm(worldUV * 0.5);      // Large features
    float mediumNoise = fbm(worldUV * 2.0);     // Medium detail
    float fineNoise = fbm(worldUV * 8.0);       // Fine grain

    float combinedNoise = largeNoise * 0.5 + mediumNoise * 0.35 + fineNoise * 0.15;

    // Base color from elevation with noise
    vec3 baseColor = getElevationColor(fragElevation, combinedNoise);

    // Perturb normal with noise for bumpy appearance
    vec3 normal = normalize(fragNormal);
    float bumpStrength = 0.3;
    normal.x += (fineNoise - 0.5) * bumpStrength;
    normal.z += (noise(worldUV * 10.0) - 0.5) * bumpStrength;
    normal = normalize(normal);

    // Strong directional lighting
    vec3 lightDir = normalize(vec3(0.7, 1.0, 0.4));
    float diffuse = max(dot(normal, lightDir), 0.0);
    float ambient = 0.35;

    // Add slight specular for wet/rocky areas at higher elevations
    vec3 viewDir = normalize(vec3(0.0, 1.0, 0.5));
    vec3 halfDir = normalize(lightDir + viewDir);
    float spec = pow(max(dot(normal, halfDir), 0.0), 16.0) * 0.15 * fragElevation;

    vec3 finalColor = baseColor * (diffuse * 0.65 + ambient) + vec3(spec);

    // Contour lines - more prominent
    float contourFreq = 10.0;  // Lines per elevation unit
    float contour = 1.0 - smoothstep(0.92, 0.98, fract(fragElevation * contourFreq));
    finalColor = mix(finalColor, finalColor * 0.6, contour * 0.4);

    // Edge darkening based on slope (steeper = darker)
    float slope = 1.0 - abs(dot(fragNormal, vec3(0, 1, 0)));
    finalColor *= 1.0 - slope * 0.3;

    outColor = vec4(finalColor, 1.0);
}
