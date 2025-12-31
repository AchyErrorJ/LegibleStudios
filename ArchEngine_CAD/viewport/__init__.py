"""
ArchEngine Viewport - 3D Visualization Module

Provides viewport widgets for embedding 3D visualization in PyQt6:
- VulkanViewportWidget: Direct Vulkan rendering (recommended)
- UE5ViewportWidget: UE5 texture sharing (legacy)
"""

from .viewport_widget import UE5ViewportWidget
from .viewport_bridge import ViewportBridge, IPCClient

# Vulkan widget (preferred)
try:
    from .vulkan_widget import VulkanViewportWidget
    HAS_VULKAN_WIDGET = True
except ImportError as e:
    HAS_VULKAN_WIDGET = False
    print(f"[viewport] VulkanViewportWidget not available: {e}")

__all__ = ['UE5ViewportWidget', 'ViewportBridge', 'IPCClient', 'VulkanViewportWidget', 'HAS_VULKAN_WIDGET']
