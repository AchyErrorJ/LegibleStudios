# thermal_viz.py
# Thermal visualization - heat flow, temperature gradients, condensation risk
#
# Visualizes building energy performance in real-time

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import PolyCollection
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math

from .thermal import ThermalAnalyzer, ClimateZone, Assembly, Window, HeatLossResult


# Temperature colormap: blue (cold) -> white -> red (hot)
TEMP_COLORS = LinearSegmentedColormap.from_list(
    'temperature', ['#3b82f6', '#60a5fa', '#93c5fd', '#ffffff', '#fca5a5', '#f87171', '#ef4444']
)

# Heat flow colormap: blue (heat loss) -> white (neutral) -> orange (heat gain)
HEAT_FLOW_COLORS = LinearSegmentedColormap.from_list(
    'heat_flow', ['#2563eb', '#3b82f6', '#60a5fa', '#f5f5f5', '#fb923c', '#f97316', '#ea580c']
)


@dataclass
class Room:
    """Room for thermal visualization"""
    name: str
    x: float
    y: float
    width: float
    height: float
    temp_f: float = 70.0
    wall_assembly: Assembly = None
    has_exterior_wall: List[str] = None  # ["north", "east", etc.]


class ThermalVisualizer:
    """
    Visualize thermal performance of buildings.
    Shows temperature gradients, heat flow, and condensation risk.
    """

    def __init__(self, dark_mode: bool = True):
        self.analyzer = ThermalAnalyzer()
        self.dark_mode = dark_mode

        if dark_mode:
            self.bg_color = '#1a1a2e'
            self.text_color = '#eeeeff'
            self.grid_color = '#333355'
        else:
            self.bg_color = '#ffffff'
            self.text_color = '#222222'
            self.grid_color = '#cccccc'

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

    def visualize_wall_section(
        self,
        assembly: Assembly,
        indoor_temp_f: float = 70,
        outdoor_temp_f: float = 20,
        indoor_rh: float = 40,
        wall_thickness_scale: float = 1.0,
        save_path: str = None
    ) -> Dict:
        """
        Visualize temperature gradient through a wall section.
        Shows where condensation might occur.

        Args:
            assembly: Wall assembly with R-value
            indoor_temp_f: Indoor temperature (°F)
            outdoor_temp_f: Outdoor temperature (°F)
            indoor_rh: Indoor relative humidity (%)
            wall_thickness_scale: Scale factor for wall display
            save_path: Optional path to save image

        Returns:
            Dict with analysis and figure
        """
        fig, ax = self._setup_figure(figsize=(14, 8),
                                      title=f"Wall Section: {assembly.name}")

        # Wall layers (simplified)
        # Real walls have multiple layers, we'll simulate a gradient
        thickness = assembly.thickness_in * wall_thickness_scale
        r_value = assembly.r_value

        # Calculate temperature at each point through wall
        n_points = 100
        x = np.linspace(0, thickness, n_points)

        # Linear temperature gradient (simplified)
        # In reality, it depends on R-value of each layer
        temp_gradient = np.linspace(indoor_temp_f, outdoor_temp_f, n_points)

        # Calculate dew point
        temp_c = (indoor_temp_f - 32) * 5/9
        rh = indoor_rh / 100
        a, b = 17.27, 237.7
        alpha = (a * temp_c) / (b + temp_c) + np.log(rh)
        dew_point_c = (b * alpha) / (a - alpha)
        dew_point_f = dew_point_c * 9/5 + 32

        # Find condensation plane (where temp = dew point)
        condensation_x = None
        for i, temp in enumerate(temp_gradient):
            if temp <= dew_point_f:
                condensation_x = x[i]
                break

        # Draw wall section
        wall_height = 48  # inches displayed

        # Create temperature gradient fill
        for i in range(n_points - 1):
            temp_normalized = (temp_gradient[i] - outdoor_temp_f) / (indoor_temp_f - outdoor_temp_f)
            color = TEMP_COLORS(temp_normalized)
            rect = patches.Rectangle((x[i], 0), x[i+1]-x[i], wall_height,
                                       facecolor=color, edgecolor='none')
            ax.add_patch(rect)

        # Draw wall outline
        ax.plot([0, 0], [0, wall_height], color=self.text_color, linewidth=2)
        ax.plot([thickness, thickness], [0, wall_height], color=self.text_color, linewidth=2)
        ax.plot([0, thickness], [0, 0], color=self.text_color, linewidth=2)
        ax.plot([0, thickness], [wall_height, wall_height], color=self.text_color, linewidth=2)

        # Draw temperature profile line
        temp_scaled = (temp_gradient - outdoor_temp_f) / (indoor_temp_f - outdoor_temp_f) * wall_height
        ax.plot(x, temp_scaled, color='#ffffff', linewidth=3, linestyle='-', label='Temperature')

        # Draw dew point line
        dew_scaled = (dew_point_f - outdoor_temp_f) / (indoor_temp_f - outdoor_temp_f) * wall_height
        ax.axhline(y=dew_scaled, color='#22d3ee', linewidth=2, linestyle='--', label=f'Dew Point ({dew_point_f:.0f}°F)')

        # Mark condensation zone
        if condensation_x is not None:
            ax.axvline(x=condensation_x, color='#ef4444', linewidth=2, linestyle=':')
            ax.fill_between([condensation_x, thickness], 0, wall_height,
                           color='#ef4444', alpha=0.2, label='Condensation Risk Zone')
            ax.annotate('⚠ CONDENSATION\nRISK', xy=(condensation_x + 0.5, wall_height/2),
                       color='#ef4444', fontsize=12, fontweight='bold',
                       ha='left', va='center')

        # Labels
        ax.text(-1, wall_height/2, f'INDOOR\n{indoor_temp_f}°F\n{indoor_rh}% RH',
               ha='right', va='center', color=self.text_color, fontsize=11, fontweight='bold')
        ax.text(thickness + 1, wall_height/2, f'OUTDOOR\n{outdoor_temp_f}°F',
               ha='left', va='center', color=self.text_color, fontsize=11, fontweight='bold')

        # Heat flow arrows
        arrow_y = wall_height + 5
        for i in range(5):
            ax.annotate('', xy=(thickness * 0.1, arrow_y),
                       xytext=(thickness * 0.9, arrow_y),
                       arrowprops=dict(arrowstyle='->', color='#f97316', lw=2))
        ax.text(thickness/2, arrow_y + 3, f'Heat Loss: R-{r_value}',
               ha='center', color='#f97316', fontsize=11)

        # Colorbar
        sm = plt.cm.ScalarMappable(cmap=TEMP_COLORS, norm=plt.Normalize(outdoor_temp_f, indoor_temp_f))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
        cbar.set_label('Temperature (°F)', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        # R-value annotation
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#22c55e' if condensation_x is None else '#ef4444', linewidth=2)
        status = "✓ No Condensation Risk" if condensation_x is None else "⚠ Condensation Risk"
        ax.text(0.02, 0.98, f"R-Value: {r_value}\n{status}", transform=ax.transAxes,
               fontsize=10, verticalalignment='top', fontfamily='monospace',
               color=self.text_color, bbox=props)

        ax.legend(loc='lower right', facecolor=self.bg_color, edgecolor=self.grid_color,
                 labelcolor=self.text_color)

        ax.set_xlim(-thickness*0.3, thickness*1.3)
        ax.set_ylim(-5, wall_height + 15)
        ax.set_xlabel('Wall Depth (inches)')
        ax.set_ylabel('Height (inches) / Temperature Scale')
        ax.set_aspect('equal')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        return {
            'condensation_risk': condensation_x is not None,
            'dew_point_f': dew_point_f,
            'condensation_depth_in': condensation_x,
            'figure': fig
        }

    def visualize_floor_plan_heat(
        self,
        rooms: List[Room],
        outdoor_temp_f: float = 20,
        climate_zone: ClimateZone = ClimateZone.ZONE_5,
        save_path: str = None
    ) -> Dict:
        """
        Visualize heat loss across a floor plan.
        Shows which rooms/walls lose most heat.

        Args:
            rooms: List of Room objects with positions
            outdoor_temp_f: Outdoor temperature
            climate_zone: IECC climate zone
            save_path: Optional save path

        Returns:
            Dict with analysis and figure
        """
        fig, ax = self._setup_figure(figsize=(14, 10),
                                      title=f"Floor Plan Heat Loss Analysis (Outdoor: {outdoor_temp_f}°F)")

        total_width = max(r.x + r.width for r in rooms)
        total_height = max(r.y + r.height for r in rooms)

        results = []

        for room in rooms:
            # Calculate heat loss for this room
            delta_t = room.temp_f - outdoor_temp_f

            # Estimate heat loss based on exterior walls
            exterior_length = 0
            if room.has_exterior_wall:
                for wall in room.has_exterior_wall:
                    if wall in ['north', 'south']:
                        exterior_length += room.width
                    else:
                        exterior_length += room.height

            wall_r = room.wall_assembly.r_value if room.wall_assembly else 13
            wall_area = exterior_length * 9  # Assume 9ft ceiling
            heat_loss = wall_area * (1/wall_r) * delta_t if wall_r > 0 else 0

            results.append({
                'room': room.name,
                'heat_loss': heat_loss,
                'temp': room.temp_f
            })

            # Color room by heat loss rate
            max_loss = 5000  # Normalize
            loss_ratio = min(heat_loss / max_loss, 1.0)

            # Blue (cool/efficient) to red (hot/losing heat)
            room_color = HEAT_FLOW_COLORS(0.5 + loss_ratio * 0.5)

            rect = patches.FancyBboxPatch(
                (room.x, room.y), room.width, room.height,
                boxstyle="round,pad=0.1,rounding_size=0.5",
                facecolor=room_color, edgecolor=self.text_color, linewidth=2
            )
            ax.add_patch(rect)

            # Room label
            ax.text(room.x + room.width/2, room.y + room.height/2,
                   f"{room.name}\n{room.temp_f}°F\n{heat_loss:.0f} BTU/hr",
                   ha='center', va='center', color=self.text_color,
                   fontsize=10, fontweight='bold')

            # Draw heat flow arrows on exterior walls
            if room.has_exterior_wall:
                arrow_color = '#f97316'
                arrow_len = 2
                for wall in room.has_exterior_wall:
                    if wall == 'north':
                        for i in range(int(room.width/4)):
                            ax.annotate('', xy=(room.x + 2 + i*4, room.y + room.height + arrow_len),
                                       xytext=(room.x + 2 + i*4, room.y + room.height),
                                       arrowprops=dict(arrowstyle='->', color=arrow_color, lw=1.5))
                    elif wall == 'south':
                        for i in range(int(room.width/4)):
                            ax.annotate('', xy=(room.x + 2 + i*4, room.y - arrow_len),
                                       xytext=(room.x + 2 + i*4, room.y),
                                       arrowprops=dict(arrowstyle='->', color=arrow_color, lw=1.5))
                    elif wall == 'east':
                        for i in range(int(room.height/4)):
                            ax.annotate('', xy=(room.x + room.width + arrow_len, room.y + 2 + i*4),
                                       xytext=(room.x + room.width, room.y + 2 + i*4),
                                       arrowprops=dict(arrowstyle='->', color=arrow_color, lw=1.5))
                    elif wall == 'west':
                        for i in range(int(room.height/4)):
                            ax.annotate('', xy=(room.x - arrow_len, room.y + 2 + i*4),
                                       xytext=(room.x, room.y + 2 + i*4),
                                       arrowprops=dict(arrowstyle='->', color=arrow_color, lw=1.5))

        # Summary
        total_loss = sum(r['heat_loss'] for r in results)
        worst_room = max(results, key=lambda r: r['heat_loss'])

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#f97316', linewidth=2)
        summary = f"""Total Heat Loss: {total_loss:,.0f} BTU/hr
Worst Room: {worst_room['room']} ({worst_room['heat_loss']:,.0f} BTU/hr)
Climate Zone: {climate_zone.value}"""
        ax.text(0.02, 0.98, summary, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', fontfamily='monospace',
               color=self.text_color, bbox=props)

        # Colorbar
        sm = plt.cm.ScalarMappable(cmap=HEAT_FLOW_COLORS, norm=plt.Normalize(0, 5000))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
        cbar.set_label('Heat Loss (BTU/hr)', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        ax.set_xlim(-5, total_width + 5)
        ax.set_ylim(-5, total_height + 5)
        ax.set_xlabel('X (ft)')
        ax.set_ylabel('Y (ft)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, color=self.grid_color)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        return {
            'total_heat_loss': total_loss,
            'room_results': results,
            'figure': fig
        }

    def animate_heat_flow(
        self,
        indoor_temp_f: float = 70,
        outdoor_temp_f: float = 0,
        wall_r_value: float = 13,
        frames: int = 100,
        save_path: str = None
    ) -> animation.FuncAnimation:
        """
        Animate heat particles flowing through a wall section.
        Shows convection, conduction, and radiation.
        """
        fig, ax = self._setup_figure(figsize=(14, 8), title="Heat Flow Animation")

        wall_left = 8
        wall_right = 16
        wall_height = 20

        # Draw static elements
        # Indoor zone
        ax.fill_between([0, wall_left], 0, wall_height, color='#fca5a5', alpha=0.3)
        ax.text(wall_left/2, wall_height + 1, f'INDOOR {indoor_temp_f}°F',
               ha='center', color='#ef4444', fontsize=12, fontweight='bold')

        # Wall
        ax.fill_between([wall_left, wall_right], 0, wall_height, color='#4a4a6a', alpha=0.8)
        ax.text((wall_left + wall_right)/2, wall_height + 1, f'WALL R-{wall_r_value}',
               ha='center', color=self.text_color, fontsize=12, fontweight='bold')

        # Outdoor zone
        ax.fill_between([wall_right, 24], 0, wall_height, color='#93c5fd', alpha=0.3)
        ax.text((wall_right + 24)/2, wall_height + 1, f'OUTDOOR {outdoor_temp_f}°F',
               ha='center', color='#3b82f6', fontsize=12, fontweight='bold')

        # Heat particles
        n_particles = 30
        particles_x = np.random.uniform(1, wall_left - 1, n_particles)
        particles_y = np.random.uniform(1, wall_height - 1, n_particles)
        particles_vx = np.random.uniform(0.1, 0.3, n_particles)

        scatter = ax.scatter(particles_x, particles_y, c='#ef4444', s=50, alpha=0.8, marker='o')

        # Energy meter
        energy_bar = ax.barh([-2], [0], height=1, color='#f97316', left=0)
        ax.text(12, -2, 'Heat Transfer Rate', ha='center', va='center',
               color=self.text_color, fontsize=10)

        ax.set_xlim(-1, 25)
        ax.set_ylim(-4, wall_height + 3)
        ax.set_aspect('equal')
        ax.axis('off')

        def animate(frame):
            nonlocal particles_x, particles_y, particles_vx

            # Move particles
            particles_x += particles_vx

            # Slow down in wall (resistance)
            in_wall = (particles_x > wall_left) & (particles_x < wall_right)
            particles_vx[in_wall] *= 0.95

            # Speed up outside wall
            particles_vx[~in_wall] = np.clip(particles_vx[~in_wall] * 1.02, 0.1, 0.3)

            # Reset particles that exit
            exited = particles_x > wall_right + 2
            particles_x[exited] = np.random.uniform(1, 3, exited.sum())
            particles_y[exited] = np.random.uniform(1, wall_height - 1, exited.sum())
            particles_vx[exited] = np.random.uniform(0.1, 0.3, exited.sum())

            # Add some vertical jitter (convection)
            particles_y += np.random.uniform(-0.2, 0.2, n_particles)
            particles_y = np.clip(particles_y, 1, wall_height - 1)

            # Color based on position (temperature)
            colors = []
            for x in particles_x:
                if x < wall_left:
                    colors.append('#ef4444')  # Hot (indoor)
                elif x < wall_right:
                    t = (x - wall_left) / (wall_right - wall_left)
                    colors.append(TEMP_COLORS(1 - t))
                else:
                    colors.append('#3b82f6')  # Cold (outdoor)

            scatter.set_offsets(np.c_[particles_x, particles_y])
            scatter.set_facecolors(colors)

            # Update energy bar
            flow_rate = np.sum(in_wall) / n_particles
            energy_bar[0].set_width(flow_rate * 20)

            return scatter, energy_bar[0]

        anim = animation.FuncAnimation(fig, animate, frames=frames, interval=50, blit=True)

        if save_path:
            if save_path.endswith('.gif'):
                anim.save(save_path, writer='pillow', fps=20)
            else:
                anim.save(save_path, writer='ffmpeg', fps=20)

        return anim


# Quick test
if __name__ == "__main__":
    viz = ThermalVisualizer(dark_mode=True)

    print("Testing wall section visualization...")
    result = viz.visualize_wall_section(
        Assembly.wall_2x4_r13(),
        indoor_temp_f=70,
        outdoor_temp_f=10,
        indoor_rh=50,
        save_path="wall_section.png"
    )
    print(f"Condensation risk: {result['condensation_risk']}")
    print(f"Dew point: {result['dew_point_f']:.1f}°F")

    print("\nTesting floor plan heat visualization...")
    rooms = [
        Room("Living", 0, 0, 15, 12, 70, Assembly.wall_2x4_r13(), ["south", "west"]),
        Room("Kitchen", 15, 0, 10, 12, 68, Assembly.wall_2x4_r13(), ["south"]),
        Room("Bedroom", 0, 12, 12, 10, 68, Assembly.wall_2x4_r13(), ["north", "west"]),
        Room("Bath", 12, 12, 8, 10, 72, Assembly.wall_2x4_r13(), ["north"]),
        Room("Office", 20, 12, 10, 10, 70, Assembly.wall_2x4_r13(), ["north", "east"]),
    ]
    result = viz.visualize_floor_plan_heat(rooms, outdoor_temp_f=20, save_path="floor_heat.png")
    print(f"Total heat loss: {result['total_heat_loss']:,.0f} BTU/hr")

    plt.show()
