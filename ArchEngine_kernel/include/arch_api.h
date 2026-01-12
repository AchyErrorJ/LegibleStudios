/**
 * ArchEngine C API - For embedding in Qt/Python applications
 *
 * This provides a simple C interface that can be called from Python via ctypes
 * to embed the Vulkan renderer in a Qt widget.
 */

#ifndef ARCH_API_H
#define ARCH_API_H

#ifdef _WIN32
    #ifdef ARCHENGINE_EXPORTS
        #define ARCH_API __declspec(dllexport)
    #else
        #define ARCH_API __declspec(dllimport)
    #endif
#else
    #define ARCH_API
#endif

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the renderer with an existing window handle.
 *
 * @param hwnd The native window handle (HWND on Windows)
 * @param width Initial width
 * @param height Initial height
 * @return 0 on success, non-zero on failure
 */
ARCH_API int arch_init(void* hwnd, int width, int height);

/**
 * Shutdown the renderer and release all resources.
 */
ARCH_API void arch_shutdown(void);

/**
 * Check if renderer is initialized.
 * @return 1 if initialized, 0 otherwise
 */
ARCH_API int arch_is_initialized(void);

/**
 * Load building data from JSON string.
 * Uses the QBD JSON format.
 *
 * @param json_str The JSON string containing building data
 * @return 0 on success, non-zero on failure
 */
ARCH_API int arch_load_json(const char* json_str);

/**
 * Load building data from a file path.
 *
 * @param file_path Path to the JSON file
 * @return 0 on success, non-zero on failure
 */
ARCH_API int arch_load_file(const char* file_path);

/**
 * Render a single frame.
 * Call this from the Qt paint event or a timer.
 *
 * @return 0 on success, non-zero on failure
 */
ARCH_API int arch_render_frame(void);

/**
 * Handle window resize.
 *
 * @param width New width
 * @param height New height
 */
ARCH_API void arch_resize(int width, int height);

/**
 * Set camera position (orbit camera).
 *
 * @param yaw Horizontal angle in radians
 * @param pitch Vertical angle in radians
 * @param distance Distance from target
 */
ARCH_API void arch_set_camera(float yaw, float pitch, float distance);

/**
 * Set camera target/focus point.
 *
 * @param x Target X
 * @param y Target Y
 * @param z Target Z
 */
ARCH_API void arch_set_camera_target(float x, float y, float z);

/**
 * Reset camera to fit the current building.
 */
ARCH_API void arch_reset_camera(void);

/**
 * Set camera field of view.
 *
 * @param fov Field of view in degrees (default 45)
 */
ARCH_API void arch_set_camera_fov(float fov);

/**
 * Get current camera field of view.
 *
 * @return FOV in degrees
 */
ARCH_API float arch_get_camera_fov(void);

/**
 * Set orthographic projection mode.
 *
 * @param enabled 1 for orthographic, 0 for perspective
 */
ARCH_API void arch_set_orthographic(int enabled);

/**
 * Get orthographic mode state.
 *
 * @return 1 if orthographic, 0 if perspective
 */
ARCH_API int arch_get_orthographic(void);

/**
 * Set visualization mode.
 *
 * @param mode 0=Structural, 1=Thermal, 2=Lighting, 3=Acoustic, 4=Material, 5=Wireframe
 */
ARCH_API void arch_set_viz_mode(int mode);

/**
 * Select an element by index.
 *
 * @param element_index Index of element to select, or -1 to clear
 */
ARCH_API void arch_select_element(int element_index);

/**
 * Get the currently selected element index.
 *
 * @return Selected element index, or -1 if none selected
 */
ARCH_API int arch_get_selected_element(void);

/**
 * Pick an element at screen coordinates.
 * Uses ray casting from the camera through the given screen position.
 *
 * @param screen_x X coordinate in screen pixels (0 = left)
 * @param screen_y Y coordinate in screen pixels (0 = top)
 * @return Element index at that position, or -1 if no hit
 */
ARCH_API int arch_pick_element(int screen_x, int screen_y);

/**
 * Get the number of elements in the current building.
 *
 * @return Number of elements
 */
ARCH_API int arch_get_element_count(void);

/**
 * Get last error message.
 *
 * @return Pointer to error string (valid until next API call)
 */
ARCH_API const char* arch_get_error(void);

// =============================================================================
// Section Clipping API
// =============================================================================

/**
 * Enable or disable section clipping.
 *
 * @param enabled 1 to enable, 0 to disable
 */
ARCH_API void arch_set_clipping_enabled(int enabled);

/**
 * Get current clipping state.
 *
 * @return 1 if enabled, 0 if disabled
 */
ARCH_API int arch_get_clipping_enabled(void);

/**
 * Set the clipping axis.
 *
 * @param axis 0=X (left/right), 1=Y (up/down), 2=Z (front/back)
 */
ARCH_API void arch_set_clip_axis(int axis);

/**
 * Get the current clipping axis.
 *
 * @return Current axis (0=X, 1=Y, 2=Z)
 */
ARCH_API int arch_get_clip_axis(void);

/**
 * Set the clipping plane position along the current axis.
 *
 * @param height Position in feet
 */
ARCH_API void arch_set_clip_height(float height);

/**
 * Get the current clipping height.
 *
 * @return Current height in feet
 */
ARCH_API float arch_get_clip_height(void);

/**
 * Flip the clipping direction.
 *
 * @param flipped 1 to flip, 0 for normal
 */
ARCH_API void arch_set_clip_flipped(int flipped);

/**
 * Get the current flip state.
 *
 * @return 1 if flipped, 0 if normal
 */
ARCH_API int arch_get_clip_flipped(void);

/**
 * Quick preset: Floor plan section at specified Y height.
 * Enables clipping, sets Y axis, sets height.
 *
 * @param y_height Height in feet (e.g., 4.0 for typical floor plan)
 */
ARCH_API void arch_set_section_floor_plan(float y_height);

/**
 * Quick preset: Elevation/section cut.
 * Enables clipping on X or Z axis.
 *
 * @param axis 0=X (section looking east/west), 2=Z (section looking north/south)
 * @param position Position along axis in feet
 */
ARCH_API void arch_set_section_elevation(int axis, float position);

// =============================================================================
// Material Style API
// =============================================================================

/**
 * Set the material rendering style.
 *
 * @param style 0=Realistic (full PBR), 1=Clean (matte), 2=Schematic (flat), 3=Blueprint
 */
ARCH_API void arch_set_material_style(int style);

/**
 * Get the current material style.
 *
 * @return Current style (0-3)
 */
ARCH_API int arch_get_material_style(void);

/**
 * Set global UV/texture scale (tiling factor).
 *
 * @param scale_u Horizontal tiling (1.0 = original size, 2.0 = 2x tiling)
 * @param scale_v Vertical tiling (1.0 = original size, 2.0 = 2x tiling)
 */
ARCH_API void arch_set_uv_scale(float scale_u, float scale_v);

/**
 * Get current UV scale.
 *
 * @param out_u Pointer to store U scale
 * @param out_v Pointer to store V scale
 */
ARCH_API void arch_get_uv_scale(float* out_u, float* out_v);

/**
 * Set roughness multiplier (affects all materials).
 *
 * @param multiplier Roughness multiplier (1.0 = default, 0.5 = smoother, 2.0 = rougher)
 */
ARCH_API void arch_set_roughness_multiplier(float multiplier);

/**
 * Get roughness multiplier.
 *
 * @return Current roughness multiplier
 */
ARCH_API float arch_get_roughness_multiplier(void);

/**
 * Set metallic multiplier (affects all materials).
 *
 * @param multiplier Metallic multiplier (1.0 = default)
 */
ARCH_API void arch_set_metallic_multiplier(float multiplier);

/**
 * Get metallic multiplier.
 *
 * @return Current metallic multiplier
 */
ARCH_API float arch_get_metallic_multiplier(void);

/**
 * Set ambient occlusion strength.
 *
 * @param strength AO strength (1.0 = full, 0.0 = none)
 */
ARCH_API void arch_set_ao_strength(float strength);

/**
 * Get ambient occlusion strength.
 *
 * @return Current AO strength
 */
ARCH_API float arch_get_ao_strength(void);

// =============================================================================
// Shadows & Lighting API
// =============================================================================

/**
 * Enable or disable shadow mapping.
 *
 * @param enabled 1 to enable, 0 to disable
 */
ARCH_API void arch_set_shadows_enabled(int enabled);

/**
 * Get shadow state.
 *
 * @return 1 if enabled, 0 if disabled
 */
ARCH_API int arch_get_shadows_enabled(void);

/**
 * Set the sun/light direction.
 *
 * @param x Direction X component
 * @param y Direction Y component (negative = down)
 * @param z Direction Z component
 */
ARCH_API void arch_set_light_direction(float x, float y, float z);

/**
 * Get current light direction.
 *
 * @param out_x Pointer to store X
 * @param out_y Pointer to store Y
 * @param out_z Pointer to store Z
 */
ARCH_API void arch_get_light_direction(float* out_x, float* out_y, float* out_z);

// =============================================================================
// SSAO (Screen Space Ambient Occlusion) API
// =============================================================================

/**
 * Enable or disable SSAO.
 *
 * @param enabled 1 to enable, 0 to disable
 */
ARCH_API void arch_set_ssao_enabled(int enabled);

/**
 * Get SSAO state.
 *
 * @return 1 if enabled, 0 if disabled
 */
ARCH_API int arch_get_ssao_enabled(void);

/**
 * Set SSAO sample radius.
 *
 * @param radius Radius in world units (default ~0.5)
 */
ARCH_API void arch_set_ssao_radius(float radius);

/**
 * Get SSAO radius.
 *
 * @return Current radius
 */
ARCH_API float arch_get_ssao_radius(void);

/**
 * Set SSAO intensity/strength.
 *
 * @param intensity Intensity multiplier (default 1.0)
 */
ARCH_API void arch_set_ssao_intensity(float intensity);

/**
 * Get SSAO intensity.
 *
 * @return Current intensity
 */
ARCH_API float arch_get_ssao_intensity(void);

// =============================================================================
// Bloom API
// =============================================================================

/**
 * Enable or disable bloom effect.
 *
 * @param enabled 1 to enable, 0 to disable
 */
ARCH_API void arch_set_bloom_enabled(int enabled);

/**
 * Get bloom state.
 *
 * @return 1 if enabled, 0 if disabled
 */
ARCH_API int arch_get_bloom_enabled(void);

/**
 * Set bloom brightness threshold.
 *
 * @param threshold Minimum brightness for bloom (default ~1.0)
 */
ARCH_API void arch_set_bloom_threshold(float threshold);

/**
 * Get bloom threshold.
 *
 * @return Current threshold
 */
ARCH_API float arch_get_bloom_threshold(void);

/**
 * Set bloom intensity.
 *
 * @param intensity Bloom strength (default ~0.5)
 */
ARCH_API void arch_set_bloom_intensity(float intensity);

/**
 * Get bloom intensity.
 *
 * @return Current intensity
 */
ARCH_API float arch_get_bloom_intensity(void);

// =============================================================================
// Tonemapping & Exposure API
// =============================================================================

/**
 * Set camera exposure.
 *
 * @param exposure Exposure value (default 1.0)
 */
ARCH_API void arch_set_exposure(float exposure);

/**
 * Get current exposure.
 *
 * @return Current exposure
 */
ARCH_API float arch_get_exposure(void);

/**
 * Set tonemapping operator.
 *
 * @param mode 0=Reinhard, 1=ACES, 2=Uncharted2
 */
ARCH_API void arch_set_tonemap_mode(int mode);

/**
 * Get current tonemap mode.
 *
 * @return Current mode (0-2)
 */
ARCH_API int arch_get_tonemap_mode(void);

// =============================================================================
// Room Data Export API
// =============================================================================

/**
 * Room data structure for export to Python.
 * All coordinates in mm.
 */
typedef struct {
    char id[64];           // Room ID
    char name[128];        // Room name
    char room_type[64];    // Room type (bedroom, kitchen, etc.)
    float bounds_x;        // Bounding box X
    float bounds_y;        // Bounding box Y
    float bounds_width;    // Bounding box width
    float bounds_height;   // Bounding box height
    float center_x;        // Center X
    float center_y;        // Center Y (actually Z in 3D)
    float area;            // Area in sq ft
    int zone;              // Zone (0=Public, 1=Private, 2=Service, 3=Circulation)
} ArchRoomData;

/**
 * Get the number of rooms in the current layout.
 *
 * @return Number of rooms
 */
ARCH_API int arch_get_room_count(void);

/**
 * Get room data by index.
 *
 * @param index Room index (0 to room_count-1)
 * @param out_room Pointer to room data struct to fill
 * @return 0 on success, non-zero if index out of bounds
 */
ARCH_API int arch_get_room_data(int index, ArchRoomData* out_room);

/**
 * Get all room data at once.
 *
 * @param out_rooms Array to fill (must have space for room_count rooms)
 * @param max_rooms Maximum rooms to return
 * @return Number of rooms filled
 */
ARCH_API int arch_get_all_rooms(ArchRoomData* out_rooms, int max_rooms);

#ifdef __cplusplus
}
#endif

#endif /* ARCH_API_H */
