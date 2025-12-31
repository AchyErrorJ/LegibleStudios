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

#ifdef __cplusplus
}
#endif

#endif /* ARCH_API_H */
