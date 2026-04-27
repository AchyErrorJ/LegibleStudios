# acoustic_viz.py
# Acoustic visualization - sound propagation, reverberation, noise mapping
#
# Visualizes room acoustics and sound transmission

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection, EllipseCollection
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math

from .acoustic import (AcousticAnalyzer, OccupancyType, WallAssembly,
                       SurfaceMaterial, TARGET_RT60)


# Sound level colormap: green (quiet) -> yellow -> red (loud)
SOUND_COLORS = LinearSegmentedColormap.from_list(
    'sound', ['#064e3b', '#059669', '#34d399', '#fbbf24', '#f97316', '#ef4444', '#991b1b']
)

# Absorption colormap: red (reflective) -> blue (absorptive)
ABSORPTION_COLORS = LinearSegmentedColormap.from_list(
    'absorption', ['#ef4444', '#f97316', '#fbbf24', '#a3e635', '#22c55e', '#14b8a6', '#0ea5e9']
)


@dataclass
class SoundSource:
    """Sound source for visualization"""
    x: float
    y: float
    level_db: float = 70  # Sound level in dB
    frequency_hz: float = 1000
    directivity: float = 1.0  # 1.0 = omnidirectional


@dataclass
class Surface:
    """Room surface with acoustic properties"""
    x1: float
    y1: float
    x2: float
    y2: float
    material: SurfaceMaterial
    name: str = ""


class AcousticVisualizer:
    """
    Visualize acoustic analysis results.
    Shows sound propagation, absorption, and RT60.
    """

    def __init__(self, dark_mode: bool = True):
        self.analyzer = AcousticAnalyzer()
        self.dark_mode = dark_mode

        if dark_mode:
            self.bg_color = '#0f0f1a'
            self.text_color = '#eeeeff'
            self.grid_color = '#333355'
            self.wall_color = '#4a4a6a'
        else:
            self.bg_color = '#ffffff'
            self.text_color = '#222222'
            self.grid_color = '#cccccc'
            self.wall_color = '#888888'

    def _setup_figure(self, figsize=(12, 8), title=""):
        """Setup matplotlib figure with styling"""
        fig, ax = plt.subplots(figsize=figsize, facecolor=self.bg_color)
        ax.set_facecolor(self.bg_color)
        ax.tick_params(colors=self.text_color)
        ax.xaxis.label.set_color(self.text_color)
        ax.yaxis.label.set_color(self.text_color)
        ax.title.set_color(self.text_color)
        for spine in ax.spines.values():
            spine.set_color(self.grid_color)
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        return fig, ax

    def visualize_sound_propagation(
        self,
        room_width: float,
        room_depth: float,
        source: SoundSource,
        surfaces: List[Surface] = None,
        show_reflections: bool = True,
        grid_resolution: float = 0.5,
        save_path: str = None
    ) -> Dict:
        """
        Visualize sound level distribution in a room.
        Shows inverse square law falloff and early reflections.

        Args:
            room_width: Room width (ft)
            room_depth: Room depth (ft)
            source: Sound source location and properties
            surfaces: Optional list of surfaces with materials
            show_reflections: Whether to show reflection paths
            grid_resolution: Grid cell size (ft)
            save_path: Optional save path

        Returns:
            Dict with SPL data and figure
        """
        fig, ax = self._setup_figure(figsize=(14, 10),
                                      title=f"Sound Propagation - {source.level_db} dB Source")

        # Create calculation grid
        x = np.arange(0, room_width, grid_resolution)
        y = np.arange(0, room_depth, grid_resolution)
        X, Y = np.meshgrid(x, y)

        # Calculate distance from source
        dx = X - source.x
        dy = Y - source.y
        distance = np.sqrt(dx**2 + dy**2)
        distance = np.maximum(distance, 0.5)  # Minimum 0.5 ft

        # Sound level using inverse square law
        # SPL = source_level - 20*log10(distance) - 11 (for point source in free field)
        spl_direct = source.level_db - 20 * np.log10(distance) - 11

        # Add reverberant field contribution (simplified)
        # This would normally come from RT60 calculation
        room_volume = room_width * room_depth * 9  # Assume 9ft ceiling
        avg_absorption = 0.2  # Assume average
        room_constant = (avg_absorption * room_width * room_depth * 2 +
                        avg_absorption * (room_width + room_depth) * 2 * 9) / (1 - avg_absorption)
        reverberant_spl = source.level_db + 10 * np.log10(4 / room_constant) if room_constant > 0 else 0

        # Total SPL (energy sum)
        spl_total = 10 * np.log10(10**(spl_direct/10) + 10**(reverberant_spl/10))
        spl_total = np.clip(spl_total, 20, 100)

        # Plot SPL distribution
        im = ax.pcolormesh(X, Y, spl_total, cmap=SOUND_COLORS, shading='auto',
                          vmin=30, vmax=80)

        # Draw room outline
        room_outline = patches.Rectangle((0, 0), room_width, room_depth,
                                          fill=False, edgecolor=self.text_color, linewidth=2)
        ax.add_patch(room_outline)

        # Draw surfaces with absorption coloring
        if surfaces:
            for surface in surfaces:
                # Get average absorption coefficient
                avg_alpha = np.mean(list(surface.material.absorption_coefficients.values()))

                ax.plot([surface.x1, surface.x2], [surface.y1, surface.y2],
                       color=ABSORPTION_COLORS(avg_alpha), linewidth=8,
                       solid_capstyle='round', label=f'{surface.name}: α={avg_alpha:.2f}')

        # Draw source
        ax.plot(source.x, source.y, 'o', color='#ffffff', markersize=15,
               markeredgecolor='#ef4444', markeredgewidth=3, zorder=10)
        ax.annotate(f'SOURCE\n{source.level_db} dB',
                   xy=(source.x, source.y),
                   xytext=(source.x + 2, source.y + 2),
                   color=self.text_color, fontsize=10, fontweight='bold',
                   arrowprops=dict(arrowstyle='->', color=self.text_color))

        # Draw reflection paths
        if show_reflections:
            # First order reflections off walls
            walls = [
                (0, source.y, 'left'),
                (room_width, source.y, 'right'),
                (source.x, 0, 'bottom'),
                (source.x, room_depth, 'top')
            ]

            for wall_x, wall_y, name in walls:
                # Mirror source position
                if name in ['left', 'right']:
                    mirror_x = -source.x if name == 'left' else 2*room_width - source.x
                    mirror_y = source.y
                    wall_point = (0 if name == 'left' else room_width, source.y)
                else:
                    mirror_x = source.x
                    mirror_y = -source.y if name == 'bottom' else 2*room_depth - source.y
                    wall_point = (source.x, 0 if name == 'bottom' else room_depth)

                # Draw reflection ray to center of room
                center = (room_width/2, room_depth/2)
                ax.plot([source.x, wall_point[0], center[0]],
                       [source.y, wall_point[1], center[1]],
                       '--', color='#6366f1', alpha=0.5, linewidth=1)

        # Contour lines
        contours = ax.contour(X, Y, spl_total, levels=[40, 50, 60, 70],
                             colors=['#22c55e', '#84cc16', '#eab308', '#ef4444'],
                             linewidths=1.5)
        ax.clabel(contours, inline=True, fontsize=9, fmt='%d dB')

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label('Sound Pressure Level (dB)', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        # Statistics
        avg_spl = np.mean(spl_total)
        max_spl = np.max(spl_total)
        min_spl = np.min(spl_total)

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#6366f1', linewidth=2)
        info = f"""Average SPL: {avg_spl:.0f} dB
Max SPL: {max_spl:.0f} dB
Min SPL: {min_spl:.0f} dB
Reverberant Level: {reverberant_spl:.0f} dB"""
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', fontfamily='monospace',
               color=self.text_color, bbox=props)

        ax.set_xlim(-1, room_width + 1)
        ax.set_ylim(-1, room_depth + 1)
        ax.set_xlabel('Width (ft)')
        ax.set_ylabel('Depth (ft)')
        ax.set_aspect('equal')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        return {
            'average_spl': avg_spl,
            'max_spl': max_spl,
            'min_spl': min_spl,
            'spl_grid': spl_total,
            'figure': fig
        }

    def visualize_rt60(
        self,
        room_volume_cuft: float,
        surfaces: List[Dict],
        occupancy_type: OccupancyType,
        save_path: str = None
    ) -> Dict:
        """
        Visualize reverberation time by frequency.
        Shows RT60 curve and target range.

        Args:
            room_volume_cuft: Room volume in cubic feet
            surfaces: List of {"material": SurfaceMaterial, "area_sqft": float}
            occupancy_type: Room type for target RT60
            save_path: Optional save path

        Returns:
            Dict with RT60 data and figure
        """
        # Calculate RT60
        result = self.analyzer.calculate_reverberation_time(
            room_volume_cuft, surfaces, occupancy_type, 0
        )

        fig, ax = self._setup_figure(figsize=(12, 8),
                                      title=f"Reverberation Time (RT60) - {occupancy_type.value}")

        frequencies = list(result.rt60_by_frequency.keys())
        rt60_values = list(result.rt60_by_frequency.values())

        # Plot RT60 curve
        ax.plot(frequencies, rt60_values, 'o-', color='#6366f1', linewidth=3,
               markersize=10, label='Calculated RT60')

        # Target range
        target_min, target_max = result.target_range
        ax.axhspan(target_min, target_max, color='#22c55e', alpha=0.2,
                  label=f'Target Range ({target_min}-{target_max}s)')
        ax.axhline(y=target_min, color='#22c55e', linestyle='--', linewidth=2)
        ax.axhline(y=target_max, color='#22c55e', linestyle='--', linewidth=2)

        # Mark out-of-range points
        for freq, rt in zip(frequencies, rt60_values):
            if rt < target_min or rt > target_max:
                ax.plot(freq, rt, 'o', color='#ef4444', markersize=15, zorder=5)
                if rt > target_max:
                    ax.annotate('Too reverberant', xy=(freq, rt),
                               xytext=(freq * 1.1, rt + 0.1),
                               color='#ef4444', fontsize=9)
                else:
                    ax.annotate('Too dead', xy=(freq, rt),
                               xytext=(freq * 1.1, rt - 0.1),
                               color='#ef4444', fontsize=9)

        # Fill area under curve
        ax.fill_between(frequencies, 0, rt60_values, color='#6366f1', alpha=0.1)

        # Add frequency labels
        freq_labels = ['125\nBass', '250', '500', '1k', '2k', '4k\nTreble']
        ax.set_xticks(frequencies)
        ax.set_xticklabels(freq_labels, color=self.text_color)

        # Status indicator
        status_color = '#22c55e' if result.within_target else '#ef4444'
        status = "✓ WITHIN TARGET" if result.within_target else "✗ OUTSIDE TARGET"

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor=status_color, linewidth=2)
        info = f"""{status}
Mid-frequency RT60: {result.rt60_seconds:.2f}s
Target: {target_min:.1f} - {target_max:.1f}s
Room Volume: {room_volume_cuft:,.0f} cu.ft"""
        ax.text(0.98, 0.98, info, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', horizontalalignment='right',
               fontfamily='monospace', color=self.text_color, bbox=props)

        # Recommendations
        if result.recommendations:
            rec_text = '\n'.join([f'• {r}' for r in result.recommendations[:3]])
            ax.text(0.02, 0.02, rec_text, transform=ax.transAxes, fontsize=9,
                   verticalalignment='bottom', color='#f97316')

        ax.set_xlabel('Frequency (Hz)', fontsize=12)
        ax.set_ylabel('Reverberation Time (seconds)', fontsize=12)
        ax.set_xscale('log')
        ax.set_xlim(100, 5000)
        ax.set_ylim(0, max(rt60_values) * 1.3)
        ax.grid(True, alpha=0.3, color=self.grid_color)
        ax.legend(loc='upper right', facecolor=self.bg_color,
                 edgecolor=self.grid_color, labelcolor=self.text_color)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        return {
            'rt60': result.rt60_seconds,
            'within_target': result.within_target,
            'rt60_by_frequency': result.rt60_by_frequency,
            'figure': fig
        }

    def animate_sound_waves(
        self,
        room_width: float,
        room_depth: float,
        source: SoundSource,
        frames: int = 100,
        save_path: str = None
    ) -> animation.FuncAnimation:
        """
        Animate sound waves propagating from a source.
        Shows expanding wavefronts and reflections.
        """
        fig, ax = self._setup_figure(figsize=(12, 10), title="Sound Wave Propagation")

        # Draw room
        room_outline = patches.Rectangle((0, 0), room_width, room_depth,
                                          fill=False, edgecolor=self.wall_color, linewidth=3)
        ax.add_patch(room_outline)

        # Source marker
        ax.plot(source.x, source.y, 'o', color='#ef4444', markersize=12, zorder=10)

        # Initialize wave circles
        n_waves = 8
        waves = []
        for i in range(n_waves):
            circle = plt.Circle((source.x, source.y), 0, fill=False,
                                color='#6366f1', linewidth=2, alpha=0)
            ax.add_patch(circle)
            waves.append(circle)

        # Initialize reflection waves (mirror sources)
        mirror_sources = [
            (-source.x, source.y),  # Left wall
            (2*room_width - source.x, source.y),  # Right wall
            (source.x, -source.y),  # Bottom wall
            (source.x, 2*room_depth - source.y),  # Top wall
        ]

        reflection_waves = []
        for mx, my in mirror_sources:
            for i in range(n_waves // 2):
                circle = plt.Circle((source.x, source.y), 0, fill=False,
                                    color='#22d3ee', linewidth=1, alpha=0)
                ax.add_patch(circle)
                reflection_waves.append((circle, mx, my))

        # SPL indicator
        spl_text = ax.text(0.5, 0.02, '', transform=ax.transAxes,
                          ha='center', color=self.text_color, fontsize=12)

        ax.set_xlim(-2, room_width + 2)
        ax.set_ylim(-2, room_depth + 2)
        ax.set_aspect('equal')
        ax.axis('off')

        # Speed of sound visualization (scaled)
        wave_speed = 0.5  # ft per frame (scaled for visualization)
        wave_spacing = 3  # Distance between wave fronts

        def animate(frame):
            # Update direct waves
            for i, wave in enumerate(waves):
                radius = (frame - i * (frames // n_waves)) * wave_speed
                if radius > 0:
                    wave.set_radius(radius)
                    # Fade with distance
                    alpha = max(0, 0.8 - radius / 30)
                    wave.set_alpha(alpha)
                    # Color shift (blue to cyan as it spreads)
                    wave.set_edgecolor(SOUND_COLORS(0.3 + 0.4 * min(1, radius/20)))
                else:
                    wave.set_alpha(0)

            # Update reflection waves
            for circle, mx, my in reflection_waves:
                # Reflections start later (after hitting wall)
                delay = min(abs(mx - source.x), abs(my - source.y)) / wave_speed
                radius = (frame - delay) * wave_speed - min(abs(mx - source.x), abs(my - source.y))

                if radius > 0:
                    # Find intersection with room boundary
                    if mx < 0:
                        cx = 0
                    elif mx > room_width:
                        cx = room_width
                    else:
                        cx = source.x

                    if my < 0:
                        cy = 0
                    elif my > room_depth:
                        cy = room_depth
                    else:
                        cy = source.y

                    circle.center = (cx, cy)
                    circle.set_radius(radius)
                    alpha = max(0, 0.5 - radius / 40)
                    circle.set_alpha(alpha)
                else:
                    circle.set_alpha(0)

            # Update SPL indicator
            distance = frame * wave_speed
            if distance > 1:
                spl = source.level_db - 20 * np.log10(distance) - 11
                spl_text.set_text(f'SPL at wavefront: {spl:.0f} dB')

            return waves + [c for c, _, _ in reflection_waves] + [spl_text]

        anim = animation.FuncAnimation(fig, animate, frames=frames, interval=50, blit=True)

        if save_path:
            if save_path.endswith('.gif'):
                anim.save(save_path, writer='pillow', fps=20)
            else:
                anim.save(save_path, writer='ffmpeg', fps=20)

        return anim


# Quick test
if __name__ == "__main__":
    viz = AcousticVisualizer(dark_mode=True)

    print("Testing sound propagation visualization...")
    source = SoundSource(5, 5, 80, 500)
    surfaces = [
        Surface(0, 0, 20, 0, SurfaceMaterial.carpet(), "Floor"),
        Surface(0, 0, 0, 15, SurfaceMaterial.drywall(), "Left Wall"),
        Surface(20, 0, 20, 15, SurfaceMaterial.glass(), "Right Wall (Window)"),
    ]
    result = viz.visualize_sound_propagation(
        room_width=20, room_depth=15,
        source=source, surfaces=surfaces,
        save_path="sound_propagation.png"
    )
    print(f"Average SPL: {result['average_spl']:.0f} dB")

    print("\nTesting RT60 visualization...")
    surfaces_rt = [
        {"material": SurfaceMaterial.drywall(), "area_sqft": 800},
        {"material": SurfaceMaterial.acoustic_ceiling(), "area_sqft": 300},
        {"material": SurfaceMaterial.carpet(), "area_sqft": 300},
    ]
    result = viz.visualize_rt60(
        room_volume_cuft=2700,
        surfaces=surfaces_rt,
        occupancy_type=OccupancyType.OFFICE_PRIVATE,
        save_path="rt60.png"
    )
    print(f"RT60: {result['rt60']:.2f}s")
    print(f"Within target: {result['within_target']}")

    plt.show()
