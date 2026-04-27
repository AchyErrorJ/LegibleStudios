"""
viewport_bridge.py - Python bindings for the native viewport bridge DLL

Provides:
- IPCClient: Named pipe communication with UE5
- ViewportBridge: D3D11 shared texture to OpenGL bridge
"""

import ctypes
from ctypes import c_void_p, c_int, c_float, c_char_p, c_uint, c_int64, c_double, CFUNCTYPE, POINTER, Structure
from pathlib import Path
from typing import Optional, Callable, Tuple
import threading


# Structures matching C++ side
class TextureInfo(Structure):
    _fields_ = [
        ("handleName", ctypes.c_char * 256),
        ("width", c_int),
        ("height", c_int),
        ("format", c_int),
        ("frameNumber", c_int64),
        ("timestamp", c_double),
    ]


# Callback types
OnTextureReadyCallback = CFUNCTYPE(None, POINTER(TextureInfo))
OnTextureResizedCallback = CFUNCTYPE(None, POINTER(TextureInfo))
OnTextureDestroyedCallback = CFUNCTYPE(None)
OnFrameReadyCallback = CFUNCTYPE(None, c_int64)
OnConnectionChangedCallback = CFUNCTYPE(None, c_int)


def _find_dll() -> Path:
    """Find the native DLL."""
    # Check common locations
    search_paths = [
        Path(__file__).parent / "native" / "build" / "Release" / "archengine_viewport.dll",
        Path(__file__).parent / "native" / "build" / "Debug" / "archengine_viewport.dll",
        Path(__file__).parent / "native" / "archengine_viewport.dll",
        Path(__file__).parent / "archengine_viewport.dll",
    ]

    for path in search_paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        "archengine_viewport.dll not found. Build the native library first:\n"
        "  cd viewport/native && mkdir build && cd build\n"
        "  cmake .. && cmake --build . --config Release"
    )


class IPCClient:
    """
    Named pipe client for communicating with UE5 ArchTextureShareComponent.

    Usage:
        client = IPCClient()
        client.on_texture_ready = lambda info: print(f"Texture: {info.width}x{info.height}")
        client.connect("ArchEngine_Viewport")
    """

    _dll = None
    _dll_lock = threading.Lock()

    @classmethod
    def _load_dll(cls):
        with cls._dll_lock:
            if cls._dll is None:
                dll_path = _find_dll()
                cls._dll = ctypes.CDLL(str(dll_path))

                # Define function signatures
                cls._dll.ipc_create.restype = c_void_p
                cls._dll.ipc_destroy.argtypes = [c_void_p]
                cls._dll.ipc_connect.argtypes = [c_void_p, c_char_p]
                cls._dll.ipc_connect.restype = c_int
                cls._dll.ipc_disconnect.argtypes = [c_void_p]
                cls._dll.ipc_is_connected.argtypes = [c_void_p]
                cls._dll.ipc_is_connected.restype = c_int

                cls._dll.ipc_send_mouse_move.argtypes = [c_void_p, c_float, c_float, c_float, c_float]
                cls._dll.ipc_send_mouse_move.restype = c_int
                cls._dll.ipc_send_mouse_button.argtypes = [c_void_p, c_float, c_float, c_int, c_int]
                cls._dll.ipc_send_mouse_button.restype = c_int
                cls._dll.ipc_send_mouse_wheel.argtypes = [c_void_p, c_float, c_float, c_float]
                cls._dll.ipc_send_mouse_wheel.restype = c_int
                cls._dll.ipc_send_keyboard.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_int]
                cls._dll.ipc_send_keyboard.restype = c_int
                cls._dll.ipc_send_ping.argtypes = [c_void_p]
                cls._dll.ipc_send_ping.restype = c_int

                cls._dll.ipc_set_texture_ready_callback.argtypes = [c_void_p, OnTextureReadyCallback]
                cls._dll.ipc_set_texture_resized_callback.argtypes = [c_void_p, OnTextureResizedCallback]
                cls._dll.ipc_set_texture_destroyed_callback.argtypes = [c_void_p, OnTextureDestroyedCallback]
                cls._dll.ipc_set_frame_ready_callback.argtypes = [c_void_p, OnFrameReadyCallback]
                cls._dll.ipc_set_connection_changed_callback.argtypes = [c_void_p, OnConnectionChangedCallback]

            return cls._dll

    def __init__(self):
        self._dll = self._load_dll()
        self._handle = self._dll.ipc_create()

        # Store callbacks to prevent garbage collection
        self._callbacks = {}

        # User-facing callbacks
        self.on_texture_ready: Optional[Callable[[TextureInfo], None]] = None
        self.on_texture_resized: Optional[Callable[[TextureInfo], None]] = None
        self.on_texture_destroyed: Optional[Callable[[], None]] = None
        self.on_frame_ready: Optional[Callable[[int], None]] = None
        self.on_connection_changed: Optional[Callable[[bool], None]] = None

        # Set up internal callbacks
        self._setup_callbacks()

    def __del__(self):
        if hasattr(self, '_handle') and self._handle:
            self._dll.ipc_destroy(self._handle)

    def _setup_callbacks(self):
        """Set up C callbacks that forward to Python callbacks."""

        def on_texture_ready(info_ptr):
            if self.on_texture_ready and info_ptr:
                self.on_texture_ready(info_ptr.contents)

        def on_texture_resized(info_ptr):
            if self.on_texture_resized and info_ptr:
                self.on_texture_resized(info_ptr.contents)

        def on_texture_destroyed():
            if self.on_texture_destroyed:
                self.on_texture_destroyed()

        def on_frame_ready(frame_number):
            if self.on_frame_ready:
                self.on_frame_ready(frame_number)

        def on_connection_changed(connected):
            if self.on_connection_changed:
                self.on_connection_changed(connected != 0)

        # Create and store callback objects
        self._callbacks['texture_ready'] = OnTextureReadyCallback(on_texture_ready)
        self._callbacks['texture_resized'] = OnTextureResizedCallback(on_texture_resized)
        self._callbacks['texture_destroyed'] = OnTextureDestroyedCallback(on_texture_destroyed)
        self._callbacks['frame_ready'] = OnFrameReadyCallback(on_frame_ready)
        self._callbacks['connection_changed'] = OnConnectionChangedCallback(on_connection_changed)

        # Register with native code
        self._dll.ipc_set_texture_ready_callback(self._handle, self._callbacks['texture_ready'])
        self._dll.ipc_set_texture_resized_callback(self._handle, self._callbacks['texture_resized'])
        self._dll.ipc_set_texture_destroyed_callback(self._handle, self._callbacks['texture_destroyed'])
        self._dll.ipc_set_frame_ready_callback(self._handle, self._callbacks['frame_ready'])
        self._dll.ipc_set_connection_changed_callback(self._handle, self._callbacks['connection_changed'])

    def connect(self, pipe_name: str = "ArchEngine_Viewport") -> bool:
        """Connect to UE5 texture share component."""
        return self._dll.ipc_connect(self._handle, pipe_name.encode('utf-8')) != 0

    def disconnect(self):
        """Disconnect from UE5."""
        self._dll.ipc_disconnect(self._handle)

    @property
    def is_connected(self) -> bool:
        """Check if connected to UE5."""
        return self._dll.ipc_is_connected(self._handle) != 0

    def send_mouse_move(self, x: float, y: float, delta_x: float = 0, delta_y: float = 0) -> bool:
        """Send mouse move event to UE5."""
        return self._dll.ipc_send_mouse_move(self._handle, x, y, delta_x, delta_y) != 0

    def send_mouse_button(self, x: float, y: float, button: int, pressed: bool) -> bool:
        """Send mouse button event to UE5. Button: 0=Left, 1=Right, 2=Middle."""
        return self._dll.ipc_send_mouse_button(self._handle, x, y, button, 1 if pressed else 0) != 0

    def send_mouse_wheel(self, x: float, y: float, delta: float) -> bool:
        """Send mouse wheel event to UE5."""
        return self._dll.ipc_send_mouse_wheel(self._handle, x, y, delta) != 0

    def send_keyboard(self, key_code: int, pressed: bool,
                      shift: bool = False, ctrl: bool = False, alt: bool = False) -> bool:
        """Send keyboard event to UE5."""
        return self._dll.ipc_send_keyboard(
            self._handle, key_code,
            1 if pressed else 0,
            1 if shift else 0,
            1 if ctrl else 0,
            1 if alt else 0
        ) != 0

    def send_ping(self) -> bool:
        """Send ping to UE5."""
        return self._dll.ipc_send_ping(self._handle) != 0


class ViewportBridge:
    """
    D3D11 shared texture to OpenGL bridge.

    Usage:
        bridge = ViewportBridge()
        bridge.initialize()  # Call from OpenGL thread
        bridge.open_texture("Global\\ArchEngine_Viewport_Texture", 1920, 1080)

        # In render loop:
        if bridge.acquire():
            gl_tex = bridge.gl_texture
            # Use texture...
            bridge.release()
    """

    _dll = None
    _dll_lock = threading.Lock()

    @classmethod
    def _load_dll(cls):
        with cls._dll_lock:
            if cls._dll is None:
                dll_path = _find_dll()
                cls._dll = ctypes.CDLL(str(dll_path))

                # Define function signatures
                cls._dll.viewport_create.restype = c_void_p
                cls._dll.viewport_destroy.argtypes = [c_void_p]
                cls._dll.viewport_initialize.argtypes = [c_void_p]
                cls._dll.viewport_initialize.restype = c_int
                cls._dll.viewport_shutdown.argtypes = [c_void_p]
                cls._dll.viewport_is_initialized.argtypes = [c_void_p]
                cls._dll.viewport_is_initialized.restype = c_int

                cls._dll.viewport_open_texture.argtypes = [c_void_p, c_char_p, c_int, c_int]
                cls._dll.viewport_open_texture.restype = c_int
                cls._dll.viewport_close_texture.argtypes = [c_void_p]
                cls._dll.viewport_has_texture.argtypes = [c_void_p]
                cls._dll.viewport_has_texture.restype = c_int

                cls._dll.viewport_acquire.argtypes = [c_void_p]
                cls._dll.viewport_acquire.restype = c_int
                cls._dll.viewport_release.argtypes = [c_void_p]

                cls._dll.viewport_get_gl_texture.argtypes = [c_void_p]
                cls._dll.viewport_get_gl_texture.restype = c_uint
                cls._dll.viewport_get_width.argtypes = [c_void_p]
                cls._dll.viewport_get_width.restype = c_int
                cls._dll.viewport_get_height.argtypes = [c_void_p]
                cls._dll.viewport_get_height.restype = c_int

                cls._dll.viewport_copy_to_cpu.argtypes = [c_void_p, c_void_p, c_int]
                cls._dll.viewport_copy_to_cpu.restype = c_int
                cls._dll.viewport_has_hardware_interop.argtypes = [c_void_p]
                cls._dll.viewport_has_hardware_interop.restype = c_int

            return cls._dll

    def __init__(self):
        self._dll = self._load_dll()
        self._handle = self._dll.viewport_create()

    def __del__(self):
        if hasattr(self, '_handle') and self._handle:
            self._dll.viewport_destroy(self._handle)

    def initialize(self) -> bool:
        """Initialize D3D11 and OpenGL interop. Must be called from OpenGL thread."""
        return self._dll.viewport_initialize(self._handle) != 0

    def shutdown(self):
        """Shutdown and cleanup resources."""
        self._dll.viewport_shutdown(self._handle)

    @property
    def is_initialized(self) -> bool:
        """Check if bridge is initialized."""
        return self._dll.viewport_is_initialized(self._handle) != 0

    def open_texture(self, handle_name: str, width: int, height: int) -> bool:
        """Open a shared texture by its handle name."""
        return self._dll.viewport_open_texture(
            self._handle, handle_name.encode('utf-8'), width, height
        ) != 0

    def close_texture(self):
        """Close the current shared texture."""
        self._dll.viewport_close_texture(self._handle)

    @property
    def has_texture(self) -> bool:
        """Check if a texture is currently open."""
        return self._dll.viewport_has_texture(self._handle) != 0

    def acquire(self) -> bool:
        """Acquire the texture for rendering. Returns False if texture not available."""
        return self._dll.viewport_acquire(self._handle) != 0

    def release(self):
        """Release the texture after rendering."""
        self._dll.viewport_release(self._handle)

    @property
    def gl_texture(self) -> int:
        """Get the OpenGL texture ID."""
        return self._dll.viewport_get_gl_texture(self._handle)

    @property
    def width(self) -> int:
        """Get texture width."""
        return self._dll.viewport_get_width(self._handle)

    @property
    def height(self) -> int:
        """Get texture height."""
        return self._dll.viewport_get_height(self._handle)

    @property
    def size(self) -> Tuple[int, int]:
        """Get texture size as (width, height)."""
        return (self.width, self.height)

    def copy_to_cpu(self, buffer: ctypes.Array, pitch: int) -> bool:
        """Copy texture to CPU buffer (fallback for systems without hardware interop)."""
        return self._dll.viewport_copy_to_cpu(self._handle, buffer, pitch) != 0

    @property
    def has_hardware_interop(self) -> bool:
        """Check if WGL_NV_DX_interop is available for zero-copy sharing."""
        return self._dll.viewport_has_hardware_interop(self._handle) != 0
