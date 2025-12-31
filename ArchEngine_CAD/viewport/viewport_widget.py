"""
viewport_widget.py - PyQt6 OpenGL widget for displaying UE5 viewport

Provides UE5ViewportWidget that can be embedded in any PyQt6 application.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QKeyEvent, QSurfaceFormat
from OpenGL.GL import *
from typing import Optional
import logging

from .viewport_bridge import IPCClient, ViewportBridge, TextureInfo

logger = logging.getLogger(__name__)


class UE5ViewportWidget(QOpenGLWidget):
    """
    PyQt6 widget that displays UE5 rendered content via shared GPU texture.

    Signals:
        connected: Emitted when connection to UE5 is established
        disconnected: Emitted when connection to UE5 is lost
        texture_ready: Emitted when texture becomes available (width, height)
        frame_updated: Emitted when a new frame is received

    Usage:
        viewport = UE5ViewportWidget()
        viewport.connect_to_ue5("ArchEngine_Viewport")
        layout.addWidget(viewport)
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    texture_ready = pyqtSignal(int, int)  # width, height
    frame_updated = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        # Set up OpenGL format
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        QSurfaceFormat.setDefaultFormat(fmt)

        super().__init__(parent)

        self._ipc_client: Optional[IPCClient] = None
        self._viewport_bridge: Optional[ViewportBridge] = None
        self._texture_info: Optional[TextureInfo] = None
        self._is_connected = False
        self._frame_pending = False

        # Shader program
        self._shader_program = None
        self._vao = None
        self._vbo = None

        # Update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._check_frame)
        self._update_timer.setInterval(16)  # ~60 FPS

        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def connect_to_ue5(self, pipe_name: str = "ArchEngine_Viewport") -> bool:
        """
        Connect to UE5 texture share component.

        Args:
            pipe_name: Name of the named pipe (matches UE5 ShareName)

        Returns:
            True if connection initiated (actual connection is async)
        """
        if self._ipc_client is None:
            self._ipc_client = IPCClient()
            self._ipc_client.on_texture_ready = self._on_texture_ready
            self._ipc_client.on_texture_resized = self._on_texture_resized
            self._ipc_client.on_texture_destroyed = self._on_texture_destroyed
            self._ipc_client.on_frame_ready = self._on_frame_ready
            self._ipc_client.on_connection_changed = self._on_connection_changed

        # Connect in background thread to avoid freezing UI
        import threading
        def do_connect():
            if self._ipc_client.connect(pipe_name):
                self._update_timer.start()

        thread = threading.Thread(target=do_connect, daemon=True)
        thread.start()
        return True  # Always return True since connection is async

    def disconnect_from_ue5(self):
        """Disconnect from UE5."""
        self._update_timer.stop()
        if self._ipc_client:
            self._ipc_client.disconnect()
        if self._viewport_bridge:
            self._viewport_bridge.close_texture()
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to UE5."""
        return self._is_connected

    def initializeGL(self):
        """Initialize OpenGL resources."""
        print("[VIEWPORT DEBUG] initializeGL called")
        # Initialize viewport bridge
        self._viewport_bridge = ViewportBridge()
        if not self._viewport_bridge.initialize():
            print("[VIEWPORT DEBUG] Failed to initialize viewport bridge!")
            logger.error("Failed to initialize viewport bridge")
            return

        print(f"[VIEWPORT DEBUG] Viewport bridge initialized (hardware interop: {self._viewport_bridge.has_hardware_interop})")
        logger.info(f"Viewport bridge initialized (hardware interop: {self._viewport_bridge.has_hardware_interop})")

        # Create shader program
        self._create_shader()
        self._create_quad()

    def _create_shader(self):
        """Create the texture display shader."""
        vertex_shader = """
        #version 330 core
        layout (location = 0) in vec2 aPos;
        layout (location = 1) in vec2 aTexCoord;
        out vec2 TexCoord;
        void main() {
            gl_Position = vec4(aPos, 0.0, 1.0);
            TexCoord = aTexCoord;
        }
        """

        fragment_shader = """
        #version 330 core
        in vec2 TexCoord;
        out vec4 FragColor;
        uniform sampler2D uTexture;
        uniform vec2 uViewportSize;
        uniform vec2 uTextureSize;
        void main() {
            // Calculate aspect ratios
            float texAspect = uTextureSize.x / uTextureSize.y;
            float viewAspect = uViewportSize.x / uViewportSize.y;

            vec2 uv = TexCoord;

            // FIT MODE: Show entire texture with letterboxing (black bars)
            if (viewAspect > texAspect) {
                // Viewport wider - add black bars on sides
                float scale = texAspect / viewAspect;
                uv.x = (TexCoord.x - 0.5) / scale + 0.5;
                if (uv.x < 0.0 || uv.x > 1.0) {
                    FragColor = vec4(0.1, 0.1, 0.1, 1.0);
                    return;
                }
            } else {
                // Viewport taller - add black bars top/bottom
                float scale = viewAspect / texAspect;
                uv.y = (TexCoord.y - 0.5) / scale + 0.5;
                if (uv.y < 0.0 || uv.y > 1.0) {
                    FragColor = vec4(0.1, 0.1, 0.1, 1.0);
                    return;
                }
            }

            FragColor = texture(uTexture, uv);
        }
        """

        # Compile shaders
        vs = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs, vertex_shader)
        glCompileShader(vs)

        # Check vertex shader compilation
        status = glGetShaderiv(vs, GL_COMPILE_STATUS)
        if not status:
            log = glGetShaderInfoLog(vs)
            print(f"[VIEWPORT DEBUG] Vertex shader compilation failed: {log}")

        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, fragment_shader)
        glCompileShader(fs)

        # Check fragment shader compilation
        status = glGetShaderiv(fs, GL_COMPILE_STATUS)
        if not status:
            log = glGetShaderInfoLog(fs)
            print(f"[VIEWPORT DEBUG] Fragment shader compilation failed: {log}")

        # Link program
        self._shader_program = glCreateProgram()
        glAttachShader(self._shader_program, vs)
        glAttachShader(self._shader_program, fs)
        glLinkProgram(self._shader_program)

        # Check program linking
        status = glGetProgramiv(self._shader_program, GL_LINK_STATUS)
        if not status:
            log = glGetProgramInfoLog(self._shader_program)
            print(f"[VIEWPORT DEBUG] Shader program linking failed: {log}")
        else:
            print(f"[VIEWPORT DEBUG] Shader program created: {self._shader_program}")

        glDeleteShader(vs)
        glDeleteShader(fs)

    def _create_quad(self):
        """Create fullscreen quad for texture display."""
        import numpy as np

        # Quad vertices: position (2) + texcoord (2)
        vertices = np.array([
            # Position    # TexCoord (flipped Y for D3D->GL)
            -1.0, -1.0,   0.0, 1.0,
             1.0, -1.0,   1.0, 1.0,
             1.0,  1.0,   1.0, 0.0,
            -1.0, -1.0,   0.0, 1.0,
             1.0,  1.0,   1.0, 0.0,
            -1.0,  1.0,   0.0, 0.0,
        ], dtype=np.float32)

        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)
        print(f"[VIEWPORT DEBUG] Created VAO={self._vao}, VBO={self._vbo}")

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # Position attribute
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * 4, None)
        glEnableVertexAttribArray(0)

        # TexCoord attribute
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def paintGL(self):
        """Render the UE5 texture."""
        # Enable sRGB framebuffer for correct color output
        glEnable(GL_FRAMEBUFFER_SRGB)

        glClearColor(0.1, 0.1, 0.1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        if not self._viewport_bridge:
            return

        # Check if we need to open a texture (must happen on GL thread)
        if hasattr(self, '_pending_texture_open') and self._pending_texture_open:
            handle_name, w, h = self._pending_texture_open
            self._pending_texture_open = None
            print(f"[VIEWPORT DEBUG] Opening texture on GL thread: {handle_name}")
            result = self._viewport_bridge.open_texture(handle_name, w, h)
            print(f"[VIEWPORT DEBUG] open_texture result: {result}, has_texture: {self._viewport_bridge.has_texture}")

        if not self._viewport_bridge.has_texture:
            return

        # Try to acquire texture - track success rate
        acquired = self._viewport_bridge.acquire()
        if not hasattr(self, '_acquire_stats'):
            self._acquire_stats = [0, 0]  # [success, fail]
        if acquired:
            self._acquire_stats[0] += 1
        else:
            self._acquire_stats[1] += 1
            # DEBUG: Draw anyway to test shader (bypass acquire)
            # return

        # Debug: track paint calls
        if not hasattr(self, '_paint_count'):
            self._paint_count = 0
            self._last_paint_log = 0
        self._paint_count += 1

        # Log periodically to verify paintGL is being called
        import time
        now = time.time()
        if now - self._last_paint_log > 2.0:  # Log every 2 seconds
            acq_success = self._acquire_stats[0] if hasattr(self, '_acquire_stats') else 0
            acq_fail = self._acquire_stats[1] if hasattr(self, '_acquire_stats') else 0
            print(f"[VIEWPORT DEBUG] paintGL called {self._paint_count} times, acquire success={acq_success} fail={acq_fail}, shader={self._shader_program}")
            # Check for GL errors
            err = glGetError()
            if err != GL_NO_ERROR:
                print(f"[VIEWPORT DEBUG] GL Error before draw: {err}")
            self._last_paint_log = now

        try:
            # Bind shader and texture
            glUseProgram(self._shader_program)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._viewport_bridge.gl_texture)

            # Set texture uniform (important!)
            tex_loc = glGetUniformLocation(self._shader_program, "uTexture")
            if tex_loc >= 0:
                glUniform1i(tex_loc, 0)

            # Set viewport and texture size uniforms for aspect ratio correction
            viewport_loc = glGetUniformLocation(self._shader_program, "uViewportSize")
            if viewport_loc >= 0:
                glUniform2f(viewport_loc, float(self.width()), float(self.height()))

            texture_loc = glGetUniformLocation(self._shader_program, "uTextureSize")
            if texture_loc >= 0:
                tex_w = self._viewport_bridge.width if self._viewport_bridge else 1920
                tex_h = self._viewport_bridge.height if self._viewport_bridge else 1080
                glUniform2f(texture_loc, float(tex_w), float(tex_h))

                # Debug aspect ratio info
                if not hasattr(self, '_aspect_logged') or now - self._aspect_logged > 5.0:
                    view_aspect = self.width() / max(self.height(), 1)
                    tex_aspect = tex_w / max(tex_h, 1)
                    print(f"[VIEWPORT DEBUG] Viewport: {self.width()}x{self.height()} ({view_aspect:.2f}), Texture: {tex_w}x{tex_h} ({tex_aspect:.2f})")
                    self._aspect_logged = now

            # Draw quad
            glBindVertexArray(self._vao)
            glDrawArrays(GL_TRIANGLES, 0, 6)
            glBindVertexArray(0)

            # Check for GL errors after draw
            err = glGetError()
            if err != GL_NO_ERROR and not hasattr(self, '_gl_error_logged'):
                print(f"[VIEWPORT DEBUG] GL Error after draw: {err}")
                self._gl_error_logged = True

        finally:
            if acquired:
                self._viewport_bridge.release()

        self._frame_pending = False

    def resizeGL(self, width: int, height: int):
        """Handle resize."""
        glViewport(0, 0, width, height)

    def sizeHint(self) -> QSize:
        """Preferred size based on texture."""
        if self._texture_info:
            return QSize(self._texture_info.width, self._texture_info.height)
        return QSize(800, 600)

    # === Event Handlers ===

    def mouseMoveEvent(self, event: QMouseEvent):
        """Forward mouse move to UE5."""
        if self._ipc_client and self._is_connected:
            pos = event.position()
            self._ipc_client.send_mouse_move(pos.x(), pos.y())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Forward mouse press to UE5."""
        if self._ipc_client and self._is_connected:
            pos = event.position()
            button = self._qt_button_to_ue5(event.button())
            self._ipc_client.send_mouse_button(pos.x(), pos.y(), button, True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Forward mouse release to UE5."""
        if self._ipc_client and self._is_connected:
            pos = event.position()
            button = self._qt_button_to_ue5(event.button())
            self._ipc_client.send_mouse_button(pos.x(), pos.y(), button, False)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Forward mouse wheel to UE5."""
        if self._ipc_client and self._is_connected:
            pos = event.position()
            delta = event.angleDelta().y() / 120.0  # Normalize to clicks
            self._ipc_client.send_mouse_wheel(pos.x(), pos.y(), delta)
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Forward key press to UE5."""
        if self._ipc_client and self._is_connected:
            mods = event.modifiers()
            self._ipc_client.send_keyboard(
                event.key(),
                True,
                bool(mods & Qt.KeyboardModifier.ShiftModifier),
                bool(mods & Qt.KeyboardModifier.ControlModifier),
                bool(mods & Qt.KeyboardModifier.AltModifier)
            )
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """Forward key release to UE5."""
        if self._ipc_client and self._is_connected:
            mods = event.modifiers()
            self._ipc_client.send_keyboard(
                event.key(),
                False,
                bool(mods & Qt.KeyboardModifier.ShiftModifier),
                bool(mods & Qt.KeyboardModifier.ControlModifier),
                bool(mods & Qt.KeyboardModifier.AltModifier)
            )
        super().keyReleaseEvent(event)

    def _qt_button_to_ue5(self, button: Qt.MouseButton) -> int:
        """Convert Qt mouse button to UE5 button index."""
        if button == Qt.MouseButton.LeftButton:
            return 0
        elif button == Qt.MouseButton.RightButton:
            return 1
        elif button == Qt.MouseButton.MiddleButton:
            return 2
        return 0

    # === IPC Callbacks ===

    def _on_texture_ready(self, info: TextureInfo):
        """Handle texture ready notification from UE5."""
        self._texture_info = info
        handle_name = info.handleName.decode('utf-8').rstrip('\x00')
        print(f"[VIEWPORT DEBUG] Texture ready: {info.width}x{info.height}, handle: '{handle_name}'")
        logger.info(f"Texture ready: {info.width}x{info.height}, handle: {handle_name}")

        # Store info for opening on main thread (OpenGL context required)
        self._pending_texture_open = (handle_name, info.width, info.height)

        # Signal main thread to open texture
        self.texture_ready.emit(info.width, info.height)

    def _on_texture_resized(self, info: TextureInfo):
        """Handle texture resize notification."""
        self._texture_info = info
        handle_name = info.handleName.decode('utf-8')
        logger.info(f"Texture resized: {info.width}x{info.height}")

        # Reopen texture with new size
        if self._viewport_bridge:
            self._viewport_bridge.close_texture()
            self._viewport_bridge.open_texture(handle_name, info.width, info.height)

        self.texture_ready.emit(info.width, info.height)

    def _on_texture_destroyed(self):
        """Handle texture destroyed notification."""
        logger.info("Texture destroyed")
        if self._viewport_bridge:
            self._viewport_bridge.close_texture()
        self._texture_info = None

    def _on_frame_ready(self, frame_number: int):
        """Handle new frame notification."""
        self._frame_pending = True
        # Track frames for debugging
        if not hasattr(self, '_frame_count'):
            self._frame_count = 0
            self._last_frame_log = 0
        self._frame_count += 1
        import time
        now = time.time()
        if now - self._last_frame_log > 2.0:  # Log every 2 seconds
            print(f"[VIEWPORT DEBUG] Frames received: {self._frame_count}")
            self._last_frame_log = now

    def _on_connection_changed(self, connected: bool):
        """Handle connection state change."""
        self._is_connected = connected
        if connected:
            print("[VIEWPORT DEBUG] Connected to UE5!")
            logger.info("Connected to UE5")
            self.connected.emit()
        else:
            print("[VIEWPORT DEBUG] Disconnected from UE5")
            logger.info("Disconnected from UE5")
            self.disconnected.emit()

    def _check_frame(self):
        """Timer callback to check for new frames."""
        # Always update to ensure viewport refreshes
        self.update()  # Trigger repaint
        if self._frame_pending:
            self._frame_pending = False
            self.frame_updated.emit()
