"""Real-time synchronization with UE5 and Vulkan renderer"""

try:
    from .livesync_server import LiveSyncServer, get_livesync_server
    HAS_LIVESYNC = True
except ImportError as e:
    HAS_LIVESYNC = False
    print(f"[sync] LiveSync not available: {e}")

try:
    from .vulkan_sync import VulkanSyncClient, get_vulkan_sync_client
    HAS_VULKAN_SYNC = True
except ImportError as e:
    HAS_VULKAN_SYNC = False
    print(f"[sync] VulkanSync not available: {e}")
