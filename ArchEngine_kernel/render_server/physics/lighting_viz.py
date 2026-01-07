# lighting_viz.py
# Lighting visualization - daylight rays, lux distribution, glare zones
#
# Visualizes natural and artificial lighting in spaces

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.collections import LineCollection
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math

from .lighting import LightingAnalyzer, SpaceType, RECOMMENDED_LUX


# Lux colormap: dark blue (dim) -> yellow (bright) -> white (very bright)
LUX_COLORS = LinearSegmentedColormap.from_list(
    'lux', ['#1e1b4b', '#312e81', '#4338ca', '#6366f1', '#fbbf24', '#fef08a', '#ffffff']
)

# Daylight colormap: warm yellow/orange for sunlight
DAYLIGHT_COLORS = LinearSegmentedColormap.from_list(
    'daylight', ['#1e1b4b', '#fef3c7', '#fde68a', '#fcd34d', '#fbbf24', '#ffffff']
)


@dataclass
class LightFixture:
    """Light fixture for visualization"""
    x: float
    y: float
    lumens: int
    beam_angle: float = 120  # degrees
    height: float = 9  # feet above floor


@dataclass
class WindowDef:
    """Window definition for daylighting"""
    x: float
    y: float
    width: float
    height: float
    orientation: str  # "N", "E", "S", "W"
    transmittance: float = 0.6


class LightingVisualizer:
    """
    Visualize lighting analysis results.
    Shows daylight distribution, artificial lighting, and glare.
    """

    def __init__(self, dark_mode: bool = True):
        self.analyzer = LightingAnalyzer()
        self.dark_mode = dark_mode

        if dark_mode:
            self.bg_color = '#0f0f1a'
            self.text_color = '#eeeeff'
            self.grid_color = '#333355'
            self.wall_color = '#2a2a4a'
        else:
            self.bg_color = '#f5f5f5'
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

    def visualize_daylight_rays(
        self,
        room_width: float,
        room_depth: float,
        room_height: float,
        windows: List[WindowDef],
        sun_altitude: float = 45,  # degrees
        sun_azimuth: float = 180,  # degrees (180 = south)
        save_path: str = None
    ) -> Dict:
        """
        Visualize daylight rays entering through windows.
        Side section view showing light penetration.

        Args:
            room_width: Room width (ft)
            room_depth: Room depth perpendicular to window (ft)
            room_height: Floor to ceiling (ft)
            windows: List of window definitions
            sun_altitude: Sun angle above horizon (degrees)
            sun_azimuth: Sun compass direction (degrees)
            save_path: Optional save path

        Returns:
            Dict with visualization data
        """
        fig, ax = self._setup_figure(figsize=(14, 8),
                                      title=f"Daylight Analysis - Sun Alt: {sun_altitude}°")

        # Draw room section (side view)
        # Floor
        ax.fill_between([0, room_depth], 0, -0.5, color=self.wall_color)
        # Back wall
        ax.fill_between([room_depth, room_depth + 0.5], 0, room_height, color=self.wall_color)
        # Ceiling
        ax.fill_between([0, room_depth], room_height, room_height + 0.5, color=self.wall_color)
        # Front wall (with window opening)
        ax.fill_between([-0.5, 0], 0, room_height, color=self.wall_color)

        # Calculate sun rays
        sun_angle_rad = math.radians(sun_altitude)

        # Draw rays from window
        n_rays = 15
        ray_colors = []
        ray_segments = []

        for window in windows:
            window_bottom = window.y
            window_top = window.y + window.height

            for i in range(n_rays):
                # Ray start at window
                y_start = window_bottom + (window_top - window_bottom) * (i / (n_rays - 1))
                x_start = 0

                # Ray travels into room at sun angle
                ray_length = room_depth * 2
                x_end = x_start + ray_length * math.cos(sun_angle_rad)
                y_end = y_start - ray_length * math.sin(sun_angle_rad)

                # Clip to room boundaries
                if y_end < 0:  # Hits floor
                    t = y_start / (y_start - y_end)
                    x_end = x_start + t * (x_end - x_start)
                    y_end = 0

                if x_end > room_depth:  # Hits back wall
                    t = (room_depth - x_start) / (x_end - x_start)
                    y_end = y_start + t * (y_end - y_start)
                    x_end = room_depth

                ray_segments.append([(x_start, y_start), (x_end, max(0, y_end))])

                # Color intensity based on position (dimmer as it travels)
                ray_colors.append(1.0 - (i / n_rays) * 0.3)

        # Draw rays as gradient lines
        lc = LineCollection(ray_segments, cmap=DAYLIGHT_COLORS,
                           norm=plt.Normalize(0, 1), linewidths=2, alpha=0.7)
        lc.set_array(np.array(ray_colors))
        ax.add_collection(lc)

        # Draw window glass
        for window in windows:
            ax.fill_between([0, 0.2], window.y, window.y + window.height,
                           color='#60a5fa', alpha=0.3)
            ax.plot([0, 0], [window.y, window.y + window.height],
                   color='#60a5fa', linewidth=3)

        # Calculate daylight penetration depth
        penetration_depth = window.height / math.tan(sun_angle_rad) if sun_altitude > 0 else room_depth
        penetration_depth = min(penetration_depth, room_depth)

        # Shade the lit zone
        lit_zone = patches.Polygon([
            (0, 0),
            (penetration_depth, 0),
            (0, min(window.y + window.height, room_height))
        ], closed=True, facecolor='#fef08a', alpha=0.2)
        ax.add_patch(lit_zone)

        # Annotations
        ax.annotate(f'Penetration: {penetration_depth:.1f} ft',
                   xy=(penetration_depth/2, 0.5),
                   color='#fbbf24', fontsize=11, fontweight='bold',
                   ha='center')

        # Sun indicator
        sun_x = -3
        sun_y = room_height + 2
        sun = plt.Circle((sun_x, sun_y), 1, color='#fbbf24', zorder=10)
        ax.add_patch(sun)
        ax.annotate('', xy=(0, room_height/2),
                   xytext=(sun_x + 1, sun_y - 0.5),
                   arrowprops=dict(arrowstyle='->', color='#fbbf24', lw=2))

        # Daylight factor estimate
        df_result = self.analyzer.calculate_daylight_factor(
            room_width, room_depth, room_height,
            sum(w.width * w.height for w in windows),
            windows[0].height if windows else 5
        )

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#fbbf24', linewidth=2)
        info = f"""Daylight Factor: {df_result.daylight_factor_pct:.1f}%
Uniformity: {df_result.uniformity_ratio:.2f}
Criteria Met: {'✓' if df_result.meets_criteria else '✗'}"""
        ax.text(0.98, 0.98, info, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', horizontalalignment='right',
               fontfamily='monospace', color=self.text_color, bbox=props)

        ax.set_xlim(-5, room_depth + 2)
        ax.set_ylim(-2, room_height + 4)
        ax.set_xlabel('Depth (ft)')
        ax.set_ylabel('Height (ft)')
        ax.set_aspect('equal')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        return {
            'daylight_factor': df_result.daylight_factor_pct,
            'penetration_depth': penetration_depth,
            'figure': fig
        }

    def visualize_lux_distribution(
        self,
        room_width: float,
        room_depth: float,
        fixtures: List[LightFixture],
        windows: List[WindowDef] = None,
        space_type: SpaceType = SpaceType.OFFICE_GENERAL,
        grid_resolution: float = 0.5,
        save_path: str = None
    ) -> Dict:
        """
        Visualize lux distribution on floor plan (bird's eye view).
        Shows illuminance levels from fixtures and daylight.

        Args:
            room_width: Room width (ft)
            room_depth: Room depth (ft)
            fixtures: List of light fixtures
            windows: Optional list of windows for daylight contribution
            space_type: Type of space for target lux
            grid_resolution: Grid cell size (ft)
            save_path: Optional save path

        Returns:
            Dict with lux data and figure
        """
        fig, ax = self._setup_figure(figsize=(12, 10),
                                      title=f"Illuminance Distribution - {space_type.value}")

        # Create calculation grid
        x = np.arange(0, room_width, grid_resolution)
        y = np.arange(0, room_depth, grid_resolution)
        X, Y = np.meshgrid(x, y)
        lux_grid = np.zeros_like(X)

        # Calculate lux from each fixture using inverse square law
        for fixture in fixtures:
            # Distance from fixture to each point
            dx = X - fixture.x
            dy = Y - fixture.y
            distance = np.sqrt(dx**2 + dy**2 + fixture.height**2)

            # Inverse square law: E = I / d²
            # Approximate intensity from lumens
            intensity = fixture.lumens / (4 * np.pi)  # Simplified

            # Cosine factor for angle
            cos_angle = fixture.height / distance

            # Lux contribution (fc to lux conversion: 1 fc ≈ 10.76 lux)
            lux_contribution = (intensity * cos_angle) / (distance**2) * 10.76

            # Apply beam angle falloff
            horizontal_dist = np.sqrt(dx**2 + dy**2)
            angle_from_vertical = np.degrees(np.arctan2(horizontal_dist, fixture.height))
            beam_factor = np.where(angle_from_vertical < fixture.beam_angle/2, 1.0,
                                   np.exp(-(angle_from_vertical - fixture.beam_angle/2)**2 / 100))

            lux_grid += lux_contribution * beam_factor

        # Add daylight contribution from windows
        if windows:
            for window in windows:
                # Simplified daylight: decreases with distance from window
                if window.orientation in ['S', 'N']:
                    dist_from_window = Y if window.orientation == 'S' else (room_depth - Y)
                else:
                    dist_from_window = X if window.orientation == 'W' else (room_width - X)

                daylight_lux = 500 * window.transmittance * np.exp(-dist_from_window / 10)
                lux_grid += daylight_lux

        # Plot lux distribution
        target_lux = RECOMMENDED_LUX.get(space_type, 500)
        im = ax.pcolormesh(X, Y, lux_grid, cmap=LUX_COLORS, shading='auto',
                          norm=LogNorm(vmin=10, vmax=max(1000, lux_grid.max())))

        # Draw room outline
        room_outline = patches.Rectangle((0, 0), room_width, room_depth,
                                          fill=False, edgecolor=self.text_color, linewidth=2)
        ax.add_patch(room_outline)

        # Draw fixtures
        for i, fixture in enumerate(fixtures):
            ax.plot(fixture.x, fixture.y, 'o', color='#fbbf24', markersize=12,
                   markeredgecolor='white', markeredgewidth=2)
            ax.annotate(f'F{i+1}\n{fixture.lumens}lm', xy=(fixture.x, fixture.y),
                       xytext=(fixture.x + 1, fixture.y + 1),
                       color=self.text_color, fontsize=9,
                       arrowprops=dict(arrowstyle='->', color=self.text_color, lw=1))

        # Draw windows
        if windows:
            for window in windows:
                if window.orientation == 'S':
                    ax.plot([window.x, window.x + window.width], [0, 0],
                           color='#60a5fa', linewidth=5)
                elif window.orientation == 'N':
                    ax.plot([window.x, window.x + window.width], [room_depth, room_depth],
                           color='#60a5fa', linewidth=5)
                elif window.orientation == 'E':
                    ax.plot([room_width, room_width], [window.x, window.x + window.width],
                           color='#60a5fa', linewidth=5)
                elif window.orientation == 'W':
                    ax.plot([0, 0], [window.x, window.x + window.width],
                           color='#60a5fa', linewidth=5)

        # Contour lines for target lux
        contour = ax.contour(X, Y, lux_grid, levels=[target_lux],
                            colors=['#22c55e'], linewidths=2, linestyles='--')
        ax.clabel(contour, inline=True, fontsize=10, fmt=f'{target_lux} lux (target)')

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label('Illuminance (lux)', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        # Statistics
        avg_lux = np.mean(lux_grid)
        min_lux = np.min(lux_grid)
        max_lux = np.max(lux_grid)
        uniformity = min_lux / avg_lux if avg_lux > 0 else 0
        meets_target = avg_lux >= target_lux and uniformity >= 0.4

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#22c55e' if meets_target else '#ef4444', linewidth=2)
        status = "✓ MEETS TARGET" if meets_target else "✗ BELOW TARGET"
        info = f"""{status}
Target: {target_lux} lux ({space_type.value})
Average: {avg_lux:.0f} lux
Min/Max: {min_lux:.0f} / {max_lux:.0f} lux
Uniformity: {uniformity:.2f}"""
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
            'average_lux': avg_lux,
            'min_lux': min_lux,
            'max_lux': max_lux,
            'uniformity': uniformity,
            'meets_target': meets_target,
            'lux_grid': lux_grid,
            'figure': fig
        }

    def animate_sun_path(
        self,
        room_width: float,
        room_depth: float,
        room_height: float,
        window: WindowDef,
        frames: int = 48,
        save_path: str = None
    ) -> animation.FuncAnimation:
        """
        Animate sun movement and changing daylight through a day.
        Shows how light penetration changes with sun position.
        """
        fig, ax = self._setup_figure(figsize=(14, 8), title="Daily Sun Path Animation")

        # Static room elements
        ax.fill_between([0, room_depth], 0, -0.5, color=self.wall_color)
        ax.fill_between([room_depth, room_depth + 0.5], 0, room_height, color=self.wall_color)
        ax.fill_between([0, room_depth], room_height, room_height + 0.5, color=self.wall_color)
        ax.fill_between([-0.5, 0], 0, room_height, color=self.wall_color)

        # Window
        ax.fill_between([0, 0.2], window.y, window.y + window.height,
                       color='#60a5fa', alpha=0.3)

        # Initialize animated elements
        lit_zone = ax.fill([0, 0, 0], [0, 0, 0], color='#fef08a', alpha=0.3)[0]
        rays, = ax.plot([], [], color='#fbbf24', alpha=0.5, linewidth=1)
        sun = plt.Circle((-5, room_height), 1, color='#fbbf24', zorder=10)
        ax.add_patch(sun)
        time_text = ax.text(0.5, 1.05, '', transform=ax.transAxes, ha='center',
                           color=self.text_color, fontsize=14, fontweight='bold')
        penetration_text = ax.text(room_depth/2, -1.5, '', ha='center',
                                   color='#fbbf24', fontsize=11)

        ax.set_xlim(-6, room_depth + 2)
        ax.set_ylim(-3, room_height + 5)
        ax.set_aspect('equal')
        ax.axis('off')

        def animate(frame):
            # Simulate sun from 6am to 6pm
            hour = 6 + (frame / frames) * 12

            # Sun altitude (simplified: peaks at noon)
            sun_altitude = 60 * math.sin(math.pi * (hour - 6) / 12)
            sun_altitude = max(5, sun_altitude)  # Minimum 5 degrees

            # Sun position for display
            sun_x = -4 + (frame / frames) * 2
            sun_y = room_height + 1 + 2 * math.sin(math.pi * frame / frames)
            sun.center = (sun_x, sun_y)

            # Calculate light penetration
            sun_angle_rad = math.radians(sun_altitude)
            penetration = window.height / math.tan(sun_angle_rad) if sun_altitude > 5 else room_depth
            penetration = min(penetration, room_depth)

            # Update lit zone
            lit_zone.set_xy([
                [0, 0],
                [penetration, 0],
                [0, window.y + window.height]
            ])

            # Update rays
            n_rays = 8
            ray_x = []
            ray_y = []
            for i in range(n_rays):
                y_start = window.y + (window.height * i / (n_rays - 1))
                x_end = min(y_start / math.tan(sun_angle_rad), room_depth)
                y_end = max(0, y_start - x_end * math.tan(sun_angle_rad))
                ray_x.extend([0, x_end, None])
                ray_y.extend([y_start, y_end, None])
            rays.set_data(ray_x, ray_y)

            # Update text
            hour_12 = hour if hour <= 12 else hour - 12
            am_pm = 'AM' if hour < 12 else 'PM'
            time_text.set_text(f'{hour_12:.0f}:00 {am_pm} - Sun Altitude: {sun_altitude:.0f}°')
            penetration_text.set_text(f'Light Penetration: {penetration:.1f} ft')

            # Change sun color based on time
            if hour < 8 or hour > 16:
                sun.set_color('#f97316')  # Orange at sunrise/sunset
            else:
                sun.set_color('#fbbf24')  # Yellow midday

            return lit_zone, rays, sun, time_text, penetration_text

        anim = animation.FuncAnimation(fig, animate, frames=frames, interval=100, blit=True)

        if save_path:
            if save_path.endswith('.gif'):
                anim.save(save_path, writer='pillow', fps=10)
            else:
                anim.save(save_path, writer='ffmpeg', fps=10)

        return anim


# Quick test
if __name__ == "__main__":
    viz = LightingVisualizer(dark_mode=True)

    print("Testing daylight rays visualization...")
    windows = [WindowDef(0, 3, 6, 4, "S", 0.6)]
    result = viz.visualize_daylight_rays(
        room_width=15, room_depth=20, room_height=9,
        windows=windows, sun_altitude=35,
        save_path="daylight_rays.png"
    )
    print(f"Daylight factor: {result['daylight_factor']:.1f}%")
    print(f"Penetration depth: {result['penetration_depth']:.1f} ft")

    print("\nTesting lux distribution visualization...")
    fixtures = [
        LightFixture(5, 5, 3000),
        LightFixture(10, 5, 3000),
        LightFixture(5, 15, 3000),
        LightFixture(10, 15, 3000),
    ]
    result = viz.visualize_lux_distribution(
        room_width=15, room_depth=20,
        fixtures=fixtures,
        windows=[WindowDef(2, 0, 8, 5, "S")],
        space_type=SpaceType.OFFICE_GENERAL,
        save_path="lux_distribution.png"
    )
    print(f"Average lux: {result['average_lux']:.0f}")
    print(f"Meets target: {result['meets_target']}")

    plt.show()
