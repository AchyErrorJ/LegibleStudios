# detail_renderer.py
# Architectural section detail renderer
#
# Renders realistic section cuts with material hatching, dimensions,
# callouts, and thermal analysis overlay

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines
from matplotlib.patches import FancyBboxPatch, Polygon, Circle, Rectangle
from matplotlib.collections import PatchCollection, LineCollection
from matplotlib.colors import LinearSegmentedColormap
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math

from .assemblies import LayeredAssembly, Layer, Material, MaterialCategory


# Temperature colormap
TEMP_COLORS = LinearSegmentedColormap.from_list(
    'temperature', ['#3b82f6', '#60a5fa', '#93c5fd', '#ffffff', '#fca5a5', '#f87171', '#ef4444']
)


class HatchPatterns:
    """Generate architectural hatch patterns for different materials"""

    @staticmethod
    def create_wood_grain(ax, x, y, width, height, color='#b8956e', density=0.15,
                          grain_type='face'):
        """
        Draw wood grain pattern.

        Args:
            grain_type: 'face' (long grain), 'end' (end grain), 'cross' (plywood)
        """
        if grain_type == 'end':
            # End grain - concentric arcs
            num_rings = int(min(width, height) / 0.15)
            center_x = x + width / 2 + np.random.uniform(-0.1, 0.1)
            center_y = y + height / 2 + np.random.uniform(-0.1, 0.1)
            for i in range(num_rings):
                r = 0.05 + i * 0.12
                theta = np.linspace(0, 2*np.pi, 40)
                ring_x = center_x + r * np.cos(theta) * (1 + 0.1*np.sin(3*theta))
                ring_y = center_y + r * np.sin(theta) * (1 + 0.1*np.cos(5*theta))
                # Clip to bounds
                mask = (ring_x >= x) & (ring_x <= x + width) & (ring_y >= y) & (ring_y <= y + height)
                if np.any(mask):
                    ax.plot(ring_x[mask], ring_y[mask], color='#92400e', linewidth=0.3, alpha=0.5)
        elif grain_type == 'cross':
            # Plywood - alternating grain directions
            layer_height = height / 3
            for layer in range(3):
                ly = y + layer * layer_height
                lh = min(layer_height, y + height - ly)
                if layer % 2 == 0:
                    # Horizontal grain
                    for i in range(int(lh / density)):
                        y_pos = ly + i * density
                        x_pts = np.linspace(x, x + width, 15)
                        y_pts = y_pos + 0.01 * np.sin(np.linspace(0, 3*np.pi, 15))
                        ax.plot(x_pts, np.clip(y_pts, ly, ly + lh), color='#a16207', linewidth=0.25, alpha=0.4)
                else:
                    # Vertical grain (shown as short dashes)
                    for i in range(int(width / density)):
                        x_pos = x + i * density
                        ax.plot([x_pos, x_pos], [ly + 0.02, ly + lh - 0.02],
                               color='#a16207', linewidth=0.25, alpha=0.4)
        else:
            # Face grain - wavy horizontal lines with knots
            num_lines = int(height / density)
            for i in range(num_lines):
                y_pos = y + i * density + np.random.uniform(-0.02, 0.02)
                x_pts = np.linspace(x, x + width, 25)
                # More natural waviness
                wave = np.sin(np.linspace(0, 4*np.pi, 25) + np.random.uniform(0, 2*np.pi))
                wave += 0.3 * np.sin(np.linspace(0, 8*np.pi, 25) + np.random.uniform(0, np.pi))
                y_pts = y_pos + 0.015 * wave
                ax.plot(x_pts, np.clip(y_pts, y, y + height), color='#92400e', linewidth=0.3, alpha=0.45)

            # Add occasional knot
            if width > 1 and height > 1 and np.random.random() > 0.6:
                kx = np.random.uniform(x + 0.3, x + width - 0.3)
                ky = np.random.uniform(y + 0.3, y + height - 0.3)
                knot = Circle((kx, ky), 0.08, facecolor='#78350f', edgecolor='#451a03',
                             alpha=0.5, linewidth=0.3)
                ax.add_patch(knot)

    @staticmethod
    def create_insulation_batt(ax, x, y, width, height, color='#fef08a'):
        """Draw fiberglass batt insulation - fluffy wavy pattern"""
        # Multiple layers of waves for depth
        for layer in range(3):
            alpha = 0.35 - layer * 0.08
            offset = layer * 0.08
            num_waves = int(height / 0.4) + 1
            for i in range(num_waves):
                y_pos = y + i * 0.4 + offset
                x_pts = np.linspace(x, x + width, 40)
                # Irregular wave pattern
                wave = np.sin(np.linspace(0, 8*np.pi, 40) + np.random.uniform(0, np.pi))
                wave += 0.5 * np.sin(np.linspace(0, 15*np.pi, 40))
                y_pts = y_pos + 0.08 * wave
                ax.plot(x_pts, np.clip(y_pts, y, y + height), color='#ca8a04', linewidth=0.4, alpha=alpha)

    @staticmethod
    def create_cellulose(ax, x, y, width, height, color='#a3a3a3'):
        """Draw dense-pack cellulose - stippled/speckled pattern"""
        num_dots = int(width * height * 80)
        dots_x = np.random.uniform(x, x + width, num_dots)
        dots_y = np.random.uniform(y, y + height, num_dots)
        sizes = np.random.uniform(0.3, 1.5, num_dots)
        colors = np.random.choice(['#737373', '#525252', '#a3a3a3'], num_dots)
        ax.scatter(dots_x, dots_y, s=sizes, c=colors, alpha=0.4, marker='.')

    @staticmethod
    def create_rigid_insulation(ax, x, y, width, height, color='#38bdf8', foam_type='xps'):
        """Draw rigid foam pattern"""
        if foam_type == 'xps':
            # XPS - diagonal cross-hatch
            spacing = 0.25
            for offset in np.arange(-height, width + height, spacing):
                # Forward diagonal
                x1, y1 = x + offset, y
                x2, y2 = x + offset + height, y + height
                if x1 < x: y1 += (x - x1); x1 = x
                if x2 > x + width: y2 -= (x2 - x - width); x2 = x + width
                if y1 <= y + height and y2 >= y and x1 <= x + width and x2 >= x:
                    ax.plot([x1, x2], [y1, y2], color='#0284c7', linewidth=0.3, alpha=0.35)
                # Backward diagonal
                x1, y1 = x + offset, y + height
                x2, y2 = x + offset + height, y
                if x1 < x: y1 -= (x - x1); x1 = x
                if x2 > x + width: y2 += (x2 - x - width); x2 = x + width
                if y1 >= y and y2 <= y + height and x1 <= x + width and x2 >= x:
                    ax.plot([x1, x2], [y1, y2], color='#0284c7', linewidth=0.3, alpha=0.35)
        elif foam_type == 'eps':
            # EPS - small circles (beadboard)
            num_beads = int(width * height * 25)
            for _ in range(num_beads):
                bx = np.random.uniform(x, x + width)
                by = np.random.uniform(y, y + height)
                br = np.random.uniform(0.02, 0.05)
                ax.add_patch(Circle((bx, by), br, facecolor='none',
                                   edgecolor='#d4d4d4', linewidth=0.2, alpha=0.4))
        else:  # polyiso
            # Polyiso - solid with subtle texture
            for i in range(int(height / 0.2)):
                y_pos = y + i * 0.2
                ax.plot([x, x + width], [y_pos, y_pos], color='#ca8a04', linewidth=0.2, alpha=0.25)

    @staticmethod
    def create_spray_foam(ax, x, y, width, height, color='#a78bfa', foam_type='closed'):
        """Draw spray foam - irregular cellular pattern"""
        num_cells = int(width * height * 12)
        for _ in range(num_cells):
            cx = np.random.uniform(x, x + width)
            cy = np.random.uniform(y, y + height)
            cr = np.random.uniform(0.03, 0.1)
            # Irregular cell shape
            angles = np.linspace(0, 2*np.pi, 8)
            radii = cr * (1 + 0.3 * np.random.randn(8))
            pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for r, a in zip(radii, angles)]
            cell = Polygon(pts, facecolor='none', edgecolor='#7c3aed' if foam_type == 'closed' else '#a78bfa',
                          linewidth=0.25, alpha=0.35, closed=True)
            ax.add_patch(cell)

    @staticmethod
    def create_concrete(ax, x, y, width, height, color='#9ca3af', aggregate=True):
        """Draw concrete with aggregate pattern"""
        # Base stipple
        num_dots = int(width * height * 20)
        dots_x = np.random.uniform(x, x + width, num_dots)
        dots_y = np.random.uniform(y, y + height, num_dots)
        sizes = np.random.uniform(0.3, 1.5, num_dots)
        ax.scatter(dots_x, dots_y, s=sizes, c='#525252', alpha=0.25, marker='.')

        # Aggregate stones
        if aggregate:
            num_stones = int(width * height * 2)
            for _ in range(num_stones):
                sx = np.random.uniform(x + 0.1, x + width - 0.1)
                sy = np.random.uniform(y + 0.1, y + height - 0.1)
                sr = np.random.uniform(0.04, 0.12)
                # Irregular stone shape
                angles = np.linspace(0, 2*np.pi, 6)
                radii = sr * (1 + 0.2 * np.random.randn(6))
                pts = [(sx + r * np.cos(a), sy + r * np.sin(a)) for r, a in zip(radii, angles)]
                stone = Polygon(pts, facecolor='#78716c', edgecolor='#57534e',
                               linewidth=0.3, alpha=0.4, closed=True)
                ax.add_patch(stone)

    @staticmethod
    def create_masonry(ax, x, y, width, height, color='#c2410c', unit_type='brick'):
        """Draw brick or CMU masonry pattern"""
        if unit_type == 'brick':
            unit_h = 0.22  # 2.25" actual / scale
            unit_w = 0.75  # 7.5" actual / scale
            mortar = 0.035
            face_color = '#c2410c'
            edge_color = '#7c2d12'
        else:  # CMU
            unit_h = 0.75  # 7.625"
            unit_w = 1.5   # 15.625"
            mortar = 0.04
            face_color = '#a1a1aa'
            edge_color = '#71717a'

        row = 0
        y_pos = y
        while y_pos < y + height:
            offset = (row % 2) * (unit_w / 2)
            x_pos = x - offset
            while x_pos < x + width:
                bx = max(x_pos, x)
                by = y_pos
                bw = min(unit_w - mortar, x + width - bx)
                bh = min(unit_h - mortar, y + height - by)
                if bw > 0.05 and bh > 0.02:
                    # Unit with subtle color variation
                    variation = np.random.uniform(0.9, 1.1)
                    rect = Rectangle((bx, by), bw, bh, linewidth=0.4,
                                     edgecolor=edge_color, facecolor=face_color,
                                     alpha=0.7 * variation)
                    ax.add_patch(rect)
                    # Texture lines on brick
                    if unit_type == 'brick' and bw > 0.2:
                        for _ in range(2):
                            lx = np.random.uniform(bx + 0.05, bx + bw - 0.05)
                            ax.plot([lx, lx + 0.1], [by + bh*0.3, by + bh*0.7],
                                   color=edge_color, linewidth=0.2, alpha=0.3)
                x_pos += unit_w
            y_pos += unit_h
            row += 1

    @staticmethod
    def create_gypsum(ax, x, y, width, height, color='#f5f5f4'):
        """Draw drywall/gypsum board pattern"""
        # Very subtle paper texture
        num_dots = int(width * height * 15)
        dots_x = np.random.uniform(x, x + width, num_dots)
        dots_y = np.random.uniform(y, y + height, num_dots)
        ax.scatter(dots_x, dots_y, s=0.2, c='#d6d3d1', alpha=0.4, marker='.')

        # Paper face indication (subtle horizontal lines)
        for i in range(int(height / 0.3)):
            y_pos = y + i * 0.3 + np.random.uniform(-0.02, 0.02)
            ax.plot([x, x + width], [y_pos, y_pos], color='#e7e5e4', linewidth=0.15, alpha=0.3)

    @staticmethod
    def create_membrane(ax, x, y, width, height, color='#d4d4d4', membrane_type='wrb'):
        """Draw membrane/barrier pattern"""
        if membrane_type == 'vapor':
            # Vapor barrier - blue tint with wrinkle lines
            ax.fill_between([x, x + width], y, y + height, color='#bfdbfe', alpha=0.4)
            for i in range(3):
                y_pos = y + height * (i + 1) / 4
                x_pts = np.linspace(x, x + width, 10)
                y_pts = y_pos + 0.01 * np.sin(np.linspace(0, 4*np.pi, 10))
                ax.plot(x_pts, y_pts, color='#3b82f6', linewidth=0.4, alpha=0.5)
        elif membrane_type == 'air':
            # Air barrier - black/dark with cross pattern
            ax.fill_between([x, x + width], y, y + height, color='#374151', alpha=0.6)
        else:
            # House wrap - white with brand lines suggestion
            ax.fill_between([x, x + width], y, y + height, color='#f5f5f4', alpha=0.5)
            ax.plot([x, x + width], [y + height/2, y + height/2],
                   color='#3b82f6', linewidth=0.5, linestyle='--', alpha=0.4)

    @staticmethod
    def create_earth(ax, x, y, width, height, color='#78350f', earth_type='gravel'):
        """Draw earth/gravel/soil pattern"""
        if earth_type == 'gravel':
            num_stones = int(width * height * 8)
            for _ in range(num_stones):
                cx = np.random.uniform(x, x + width)
                cy = np.random.uniform(y, y + height)
                r = np.random.uniform(0.04, 0.12)
                # Angular gravel shape
                angles = np.linspace(0, 2*np.pi, 5 + int(np.random.uniform(0, 3)))
                radii = r * (0.7 + 0.3 * np.random.rand(len(angles)))
                pts = [(cx + ri * np.cos(a), cy + ri * np.sin(a)) for ri, a in zip(radii, angles)]
                stone = Polygon(pts, facecolor='#a8a29e', edgecolor='#78716c',
                               linewidth=0.3, alpha=0.5, closed=True)
                ax.add_patch(stone)
        else:  # soil
            # Soil with organic matter dots
            num_dots = int(width * height * 30)
            dots_x = np.random.uniform(x, x + width, num_dots)
            dots_y = np.random.uniform(y, y + height, num_dots)
            sizes = np.random.uniform(0.5, 2, num_dots)
            colors = np.random.choice(['#78350f', '#92400e', '#451a03', '#65350f'], num_dots)
            ax.scatter(dots_x, dots_y, s=sizes, c=colors, alpha=0.4, marker='.')

    @staticmethod
    def create_metal(ax, x, y, width, height, color='#64748b', metal_type='steel'):
        """Draw metal hatching pattern"""
        # Diagonal lines (standard metal hatch)
        spacing = 0.08
        for offset in np.arange(0, width + height, spacing):
            x1, y1 = x + offset, y
            x2, y2 = x, y + offset
            if x1 > x + width:
                y1 = y + (x1 - x - width)
                x1 = x + width
            if y2 > y + height:
                x2 = x + (y2 - y - height)
                y2 = y + height
            if x1 >= x and x2 <= x + width and y1 <= y + height and y2 >= y:
                ax.plot([x1, x2], [y1, y2], color='#334155', linewidth=0.3, alpha=0.5)

    @staticmethod
    def create_shingles(ax, x, y, width, height, color='#374151'):
        """Draw asphalt shingle pattern"""
        shingle_h = 0.04
        shingle_w = 0.25
        exposure = 0.04  # Visible portion

        row = 0
        y_pos = y
        while y_pos < y + height:
            offset = (row % 2) * (shingle_w / 2)
            x_pos = x - offset
            while x_pos < x + width:
                sx = max(x_pos, x)
                sw = min(shingle_w, x + width - sx)
                if sw > 0.02:
                    # Shingle tab
                    ax.plot([sx, sx + sw], [y_pos, y_pos], color='#1f2937', linewidth=0.8, alpha=0.7)
                    # Granule texture
                    for _ in range(3):
                        gx = np.random.uniform(sx, sx + sw)
                        gy = y_pos + np.random.uniform(-0.01, 0.01)
                        ax.plot(gx, gy, '.', color='#4b5563', markersize=0.5, alpha=0.4)
                x_pos += shingle_w
            y_pos += exposure
            row += 1


class DetailRenderer:
    """
    Render architectural section details.

    Creates publication-quality section drawings with:
    - Material hatching and colors
    - Dimension strings
    - Material callouts
    - Thermal gradient overlay
    - Condensation plane marking
    """

    def __init__(self, dark_mode: bool = False):
        self.dark_mode = dark_mode

        if dark_mode:
            self.bg_color = '#1a1a2e'
            self.text_color = '#eeeeff'
            self.dim_color = '#94a3b8'
            self.cut_line_color = '#ffffff'
        else:
            self.bg_color = '#ffffff'
            self.text_color = '#1f2937'
            self.dim_color = '#4b5563'
            self.cut_line_color = '#000000'

    def _setup_figure(self, figsize=(14, 10), title=""):
        """Setup figure with proper styling"""
        fig, ax = plt.subplots(figsize=figsize, facecolor=self.bg_color)
        ax.set_facecolor(self.bg_color)
        ax.tick_params(colors=self.text_color)
        ax.xaxis.label.set_color(self.text_color)
        ax.yaxis.label.set_color(self.text_color)
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold', color=self.text_color)
        return fig, ax

    def _draw_layer(self, ax, layer: Layer, x: float, y: float,
                    width: float, show_framing: bool = True):
        """Draw a single layer with appropriate hatching"""
        thickness = layer.thickness_in
        material = layer.material
        category = material.category

        # Base fill
        rect = Rectangle((x, y), width, thickness,
                         facecolor=material.color, edgecolor='none', alpha=0.8)
        ax.add_patch(rect)

        # Add hatching based on material category
        if category == MaterialCategory.WOOD:
            # Determine grain type based on context
            if thickness < 2:  # Thin like a stud in section
                HatchPatterns.create_wood_grain(ax, x, y, width, thickness, material.color, grain_type='end')
            else:
                HatchPatterns.create_wood_grain(ax, x, y, width, thickness, material.color, grain_type='face')

        elif category == MaterialCategory.INSULATION_BATT:
            HatchPatterns.create_insulation_batt(ax, x, y, width, thickness, material.color)
            # Show studs if framing layer
            if layer.is_framing_layer and show_framing and layer.framing_material:
                self._draw_framing(ax, layer, x, y, width)

        elif category == MaterialCategory.INSULATION_RIGID:
            # Determine foam type from material name
            foam_type = 'xps'
            if 'eps' in material.name.lower():
                foam_type = 'eps'
            elif 'polyiso' in material.name.lower():
                foam_type = 'polyiso'
            HatchPatterns.create_rigid_insulation(ax, x, y, width, thickness, material.color, foam_type)

        elif category == MaterialCategory.INSULATION_SPRAY:
            foam_type = 'closed' if 'closed' in material.name.lower() else 'open'
            HatchPatterns.create_spray_foam(ax, x, y, width, thickness, material.color, foam_type)

        elif category == MaterialCategory.CONCRETE:
            HatchPatterns.create_concrete(ax, x, y, width, thickness, material.color, aggregate=True)

        elif category == MaterialCategory.MASONRY:
            unit_type = 'cmu' if 'cmu' in material.name.lower() else 'brick'
            HatchPatterns.create_masonry(ax, x, y, width, thickness, material.color, unit_type)

        elif category == MaterialCategory.GYPSUM:
            HatchPatterns.create_gypsum(ax, x, y, width, thickness, material.color)

        elif category == MaterialCategory.SHEATHING:
            # Plywood/OSB cross-grain pattern
            HatchPatterns.create_wood_grain(ax, x, y, width, thickness, material.color,
                                           density=0.08, grain_type='cross')

        elif category == MaterialCategory.MEMBRANE:
            # Determine membrane type
            if 'vapor' in material.name.lower():
                membrane_type = 'vapor'
            elif 'air' in material.name.lower():
                membrane_type = 'air'
            else:
                membrane_type = 'wrb'
            HatchPatterns.create_membrane(ax, x, y, width, thickness, material.color, membrane_type)

        elif category == MaterialCategory.AIR_GAP:
            # Show as white/empty with light dashed lines
            rect.set_facecolor('#f8fafc' if not self.dark_mode else '#374151')
            rect.set_alpha(0.3)
            # Dashed lines to indicate air
            for i in range(int(thickness / 0.4) + 1):
                y_pos = y + i * 0.4
                ax.plot([x + 0.2, x + width - 0.2], [y_pos, y_pos],
                       color=self.dim_color, linewidth=0.3, linestyle=':', alpha=0.5)
            # Show studs if framing layer
            if layer.is_framing_layer and show_framing and layer.framing_material:
                self._draw_framing(ax, layer, x, y, width)

        elif category == MaterialCategory.FLOORING:
            if 'carpet' in material.name.lower():
                # Fuzzy texture for carpet
                for i in range(int(width / 0.08)):
                    x_pos = x + i * 0.08 + np.random.uniform(-0.01, 0.01)
                    h = thickness * np.random.uniform(0.5, 0.9)
                    ax.plot([x_pos, x_pos], [y, y + h],
                           color='#525252', linewidth=0.4, alpha=0.4)
            elif 'tile' in material.name.lower():
                # Tile grid with grout lines
                tile_size = 0.4
                for i in range(int(width / tile_size) + 1):
                    ax.plot([x + i * tile_size, x + i * tile_size], [y, y + thickness],
                           color='#d4d4d4', linewidth=0.8, alpha=0.6)
            else:
                HatchPatterns.create_wood_grain(ax, x, y, width, thickness, material.color, grain_type='face')

        elif category == MaterialCategory.ROOFING:
            if 'shingle' in material.name.lower():
                HatchPatterns.create_shingles(ax, x, y, width, thickness, material.color)
            elif 'metal' in material.name.lower():
                HatchPatterns.create_metal(ax, x, y, width, thickness, material.color)
                # Standing seam ridges
                for i in range(int(width / 1.5) + 1):
                    x_pos = x + i * 1.5
                    ax.plot([x_pos, x_pos], [y, y + thickness],
                           color='#1e293b', linewidth=1.5, alpha=0.7)
            else:
                # Membrane roofing
                HatchPatterns.create_membrane(ax, x, y, width, thickness, '#f1f5f9', 'wrb')

        elif category == MaterialCategory.METAL:
            HatchPatterns.create_metal(ax, x, y, width, thickness, material.color)

        elif category == MaterialCategory.EARTH:
            earth_type = 'gravel' if 'gravel' in material.name.lower() else 'soil'
            HatchPatterns.create_earth(ax, x, y, width, thickness, material.color, earth_type)

        elif category == MaterialCategory.FINISH:
            # Siding patterns
            if 'vinyl' in material.name.lower() or 'lap' in material.name.lower():
                # Horizontal lap lines
                lap_height = 0.06
                for i in range(int(thickness / lap_height) + 1):
                    y_pos = y + i * lap_height
                    ax.plot([x, x + width], [y_pos, y_pos], color='#94a3b8', linewidth=0.6, alpha=0.6)
            elif 'stucco' in material.name.lower():
                # Stipple texture
                num_dots = int(width * thickness * 40)
                dots_x = np.random.uniform(x, x + width, num_dots)
                dots_y = np.random.uniform(y, y + thickness, num_dots)
                ax.scatter(dots_x, dots_y, s=0.4, c='#a8a29e', alpha=0.5, marker='.')
            else:
                HatchPatterns.create_wood_grain(ax, x, y, width, thickness, material.color, grain_type='face')

        # Draw cut line (bold outline)
        rect_outline = Rectangle((x, y), width, thickness,
                                 facecolor='none', edgecolor=self.cut_line_color,
                                 linewidth=1.5)
        ax.add_patch(rect_outline)

    def _draw_framing(self, ax, layer: Layer, x: float, y: float, width: float):
        """Draw framing members within a framing layer"""
        spacing = layer.framing_spacing_in
        stud_width = layer.framing_width_in
        thickness = layer.thickness_in
        framing_color = layer.framing_material.color

        # Draw studs at regular spacing
        num_studs = int(width / spacing) + 1
        for i in range(num_studs):
            stud_x = x + i * spacing - stud_width / 2
            if stud_x >= x - stud_width and stud_x <= x + width:
                stud_rect = Rectangle(
                    (max(stud_x, x), y),
                    min(stud_width, x + width - max(stud_x, x)),
                    thickness,
                    facecolor=framing_color,
                    edgecolor='#78350f',
                    linewidth=0.5,
                    alpha=0.9
                )
                ax.add_patch(stud_rect)
                # Add wood grain to stud
                HatchPatterns.create_wood_grain(
                    ax, max(stud_x, x), y,
                    min(stud_width, x + width - max(stud_x, x)),
                    thickness, '#8b5a2b', density=0.2
                )

    def _draw_dimensions(self, ax, assembly: LayeredAssembly,
                         x_offset: float, start_y: float,
                         dim_offset: float = 1.5):
        """Draw dimension strings"""
        current_y = start_y

        # Individual layer dimensions (left side)
        for layer in assembly.layers:
            thickness = layer.thickness_in
            mid_y = current_y + thickness / 2

            # Dimension line
            ax.annotate('', xy=(x_offset - dim_offset, current_y),
                       xytext=(x_offset - dim_offset, current_y + thickness),
                       arrowprops=dict(arrowstyle='<->', color=self.dim_color,
                                      shrinkA=0, shrinkB=0, lw=0.8))

            # Dimension text
            if thickness >= 0.1:
                dim_text = f'{thickness:.2f}"' if thickness < 1 else f'{thickness:.1f}"'
                ax.text(x_offset - dim_offset - 0.3, mid_y, dim_text,
                       ha='right', va='center', fontsize=8, color=self.dim_color,
                       fontfamily='monospace')

            current_y += thickness

        # Total dimension (further left)
        total = assembly.total_thickness_in
        ax.annotate('', xy=(x_offset - dim_offset - 1.5, start_y),
                   xytext=(x_offset - dim_offset - 1.5, start_y + total),
                   arrowprops=dict(arrowstyle='<->', color=self.text_color,
                                  shrinkA=0, shrinkB=0, lw=1.2))
        ax.text(x_offset - dim_offset - 2.0, start_y + total/2,
               f'{total:.2f}"', ha='right', va='center', fontsize=10,
               color=self.text_color, fontweight='bold', fontfamily='monospace')

    def _draw_callouts(self, ax, assembly: LayeredAssembly,
                       x_offset: float, width: float, start_y: float,
                       callout_offset: float = 1.0):
        """Draw material callouts"""
        current_y = start_y

        for i, layer in enumerate(assembly.layers):
            thickness = layer.thickness_in
            mid_y = current_y + thickness / 2

            # Only show callout if layer is thick enough
            if thickness >= 0.2:
                # Leader line
                ax.plot([x_offset + width, x_offset + width + callout_offset],
                       [mid_y, mid_y], color=self.dim_color, linewidth=0.5)

                # Callout text
                r_val = layer.r_value
                text = f"{layer.material.name}"
                if r_val > 0.1:
                    text += f" (R-{r_val:.1f})"

                ax.text(x_offset + width + callout_offset + 0.1, mid_y,
                       text, ha='left', va='center', fontsize=8,
                       color=self.text_color, fontfamily='sans-serif')

            current_y += thickness

    def _draw_thermal_overlay(self, ax, assembly: LayeredAssembly,
                              x_offset: float, width: float, start_y: float,
                              indoor_temp_f: float, outdoor_temp_f: float,
                              indoor_rh_pct: float = 40):
        """Draw temperature gradient and condensation plane"""
        profile = assembly.get_temperature_profile(indoor_temp_f, outdoor_temp_f)

        # Draw temperature line - use positions from profile
        temps = [t for _, t, _ in profile]
        positions = [start_y + pos for pos, _, _ in profile]

        # Normalize temperature for x position
        temp_range = indoor_temp_f - outdoor_temp_f
        temp_x = []
        for temp in temps:
            normalized = (temp - outdoor_temp_f) / temp_range if temp_range > 0 else 0.5
            temp_x.append(x_offset + width + 2 + normalized * 2)

        # Draw temperature profile
        ax.plot(temp_x, positions, color='#ef4444', linewidth=2, marker='o',
               markersize=4, label='Temperature')

        # Temperature scale
        ax.text(x_offset + width + 2, start_y - 0.5, f'{outdoor_temp_f:.0f}°F',
               ha='center', va='top', fontsize=8, color='#3b82f6')
        ax.text(x_offset + width + 4, start_y - 0.5, f'{indoor_temp_f:.0f}°F',
               ha='center', va='top', fontsize=8, color='#ef4444')

        # Check for condensation
        condensation = assembly.find_condensation_plane(indoor_temp_f, outdoor_temp_f, indoor_rh_pct)
        if condensation:
            cond_y = start_y + condensation[0]
            dew_point = condensation[2]

            # Dew point line
            dew_x = x_offset + width + 2 + ((dew_point - outdoor_temp_f) / temp_range) * 2
            ax.axhline(y=cond_y, color='#22d3ee', linewidth=1.5, linestyle='--', alpha=0.8)
            ax.plot([x_offset, x_offset + width], [cond_y, cond_y],
                   color='#ef4444', linewidth=2, linestyle=':')

            # Warning marker
            ax.scatter([x_offset + width/2], [cond_y], s=100, c='#ef4444',
                      marker='X', zorder=10)
            ax.text(x_offset + width/2, cond_y + 0.3,
                   f'CONDENSATION RISK\nDew Point: {dew_point:.0f}°F',
                   ha='center', va='bottom', fontsize=9, color='#ef4444',
                   fontweight='bold')

    def render_wall_section(
        self,
        assembly: LayeredAssembly,
        section_width: float = 12.0,
        show_dimensions: bool = True,
        show_callouts: bool = True,
        show_thermal: bool = False,
        indoor_temp_f: float = 70,
        outdoor_temp_f: float = 20,
        indoor_rh_pct: float = 40,
        show_framing: bool = True,
        title: str = None,
        save_path: str = None
    ) -> Dict:
        """
        Render a wall section detail.

        Args:
            assembly: LayeredAssembly to render
            section_width: Width of section to show (inches)
            show_dimensions: Draw dimension strings
            show_callouts: Draw material callouts
            show_thermal: Draw temperature gradient overlay
            indoor_temp_f: Indoor temperature for thermal analysis
            outdoor_temp_f: Outdoor temperature
            indoor_rh_pct: Indoor relative humidity
            show_framing: Show framing members in framing layers
            title: Optional custom title
            save_path: Path to save image

        Returns:
            Dict with figure and analysis results
        """
        if title is None:
            title = f"Wall Section: {assembly.name}"

        fig, ax = self._setup_figure(figsize=(16, 12), title=title)

        x_offset = 4.0  # Leave room for dimensions
        start_y = 1.0
        width = section_width

        # Draw each layer from interior to exterior (bottom to top)
        current_y = start_y
        for layer in assembly.layers:
            self._draw_layer(ax, layer, x_offset, current_y, width, show_framing)
            current_y += layer.thickness_in

        # Interior/Exterior labels
        ax.text(x_offset + width/2, start_y - 0.8, 'INTERIOR',
               ha='center', va='top', fontsize=10, color=self.text_color,
               fontweight='bold')
        ax.text(x_offset + width/2, current_y + 0.5, 'EXTERIOR',
               ha='center', va='bottom', fontsize=10, color=self.text_color,
               fontweight='bold')

        # Dimensions
        if show_dimensions:
            self._draw_dimensions(ax, assembly, x_offset, start_y)

        # Callouts
        if show_callouts:
            self._draw_callouts(ax, assembly, x_offset, width, start_y)

        # Thermal overlay
        if show_thermal:
            self._draw_thermal_overlay(ax, assembly, x_offset, width, start_y,
                                       indoor_temp_f, outdoor_temp_f, indoor_rh_pct)

        # R-value summary box
        r_total = assembly.total_r_value
        u_factor = assembly.u_factor

        summary_text = f"Total R-Value: {r_total:.1f}\nU-Factor: {u_factor:.3f}"
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#22c55e', linewidth=2, alpha=0.9)
        ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', fontfamily='monospace',
               color=self.text_color, bbox=props)

        # Set axis limits
        total_height = assembly.total_thickness_in
        margin = 2
        ax.set_xlim(0, x_offset + width + 8)
        ax.set_ylim(start_y - 2, start_y + total_height + 2)
        ax.set_aspect('equal')
        ax.axis('off')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        return {
            'figure': fig,
            'assembly': assembly,
            'r_value': r_total,
            'u_factor': u_factor,
        }

    def render_floor_section(
        self,
        assembly: LayeredAssembly,
        section_width: float = 24.0,
        show_dimensions: bool = True,
        show_callouts: bool = True,
        show_framing: bool = True,
        title: str = None,
        save_path: str = None
    ) -> Dict:
        """
        Render a floor section detail.

        Args:
            assembly: LayeredAssembly to render
            section_width: Width of section to show (inches)
            show_dimensions: Draw dimension strings
            show_callouts: Draw material callouts
            show_framing: Show framing members
            title: Optional custom title
            save_path: Path to save image

        Returns:
            Dict with figure and analysis results
        """
        if title is None:
            title = f"Floor Section: {assembly.name}"

        fig, ax = self._setup_figure(figsize=(18, 10), title=title)

        x_offset = 3.0
        start_y = 1.0
        width = section_width

        # Draw layers (for floor, top to bottom = finish to structure)
        current_y = start_y
        for layer in assembly.layers:
            self._draw_layer(ax, layer, x_offset, current_y, width, show_framing)
            current_y += layer.thickness_in

        # Labels
        ax.text(x_offset + width/2, start_y - 0.5, 'TOP (Finish Floor)',
               ha='center', va='top', fontsize=10, color=self.text_color,
               fontweight='bold')
        ax.text(x_offset + width/2, current_y + 0.3, 'BOTTOM',
               ha='center', va='bottom', fontsize=10, color=self.text_color,
               fontweight='bold')

        if show_dimensions:
            self._draw_dimensions(ax, assembly, x_offset, start_y, dim_offset=1.0)

        if show_callouts:
            self._draw_callouts(ax, assembly, x_offset, width, start_y)

        # Summary
        total_depth = assembly.total_thickness_in
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#6366f1', linewidth=2, alpha=0.9)
        ax.text(0.02, 0.98, f"Total Depth: {total_depth:.2f}\"",
               transform=ax.transAxes, fontsize=10, verticalalignment='top',
               fontfamily='monospace', color=self.text_color, bbox=props)

        ax.set_xlim(0, x_offset + width + 6)
        ax.set_ylim(start_y - 2, start_y + total_depth + 2)
        ax.set_aspect('equal')
        ax.axis('off')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        return {
            'figure': fig,
            'assembly': assembly,
            'total_depth': total_depth,
        }

    def render_roof_section(
        self,
        assembly: LayeredAssembly,
        section_width: float = 24.0,
        roof_pitch: float = 4.0,  # Rise per 12" run (4:12 pitch)
        show_dimensions: bool = True,
        show_callouts: bool = True,
        show_framing: bool = True,
        title: str = None,
        save_path: str = None
    ) -> Dict:
        """
        Render a roof section detail (at an angle).

        Args:
            assembly: LayeredAssembly to render
            section_width: Width of section (along slope)
            roof_pitch: Rise per 12\" run
            show_dimensions: Draw dimension strings
            show_callouts: Draw material callouts
            show_framing: Show framing members
            title: Optional custom title
            save_path: Path to save image

        Returns:
            Dict with figure and analysis results
        """
        if title is None:
            title = f"Roof Section: {assembly.name}"

        fig, ax = self._setup_figure(figsize=(18, 12), title=title)

        # For simplicity, render flat like wall but add pitch indicator
        x_offset = 4.0
        start_y = 1.0
        width = section_width

        # Draw layers
        current_y = start_y
        for layer in assembly.layers:
            self._draw_layer(ax, layer, x_offset, current_y, width, show_framing)
            current_y += layer.thickness_in

        # Labels
        ax.text(x_offset + width/2, start_y - 0.5, 'INTERIOR (Ceiling)',
               ha='center', va='top', fontsize=10, color=self.text_color,
               fontweight='bold')
        ax.text(x_offset + width/2, current_y + 0.3, 'EXTERIOR (Roof)',
               ha='center', va='bottom', fontsize=10, color=self.text_color,
               fontweight='bold')

        # Pitch indicator
        pitch_angle = math.atan(roof_pitch / 12) * 180 / math.pi
        ax.text(x_offset + width + 2, current_y,
               f'Pitch: {roof_pitch:.0f}:12 ({pitch_angle:.1f}°)',
               ha='left', va='center', fontsize=9, color=self.dim_color)

        if show_dimensions:
            self._draw_dimensions(ax, assembly, x_offset, start_y)

        if show_callouts:
            self._draw_callouts(ax, assembly, x_offset, width, start_y)

        # Summary
        r_total = assembly.total_r_value
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#f59e0b', linewidth=2, alpha=0.9)
        ax.text(0.02, 0.98, f"Total R-Value: {r_total:.1f}",
               transform=ax.transAxes, fontsize=10, verticalalignment='top',
               fontfamily='monospace', color=self.text_color, bbox=props)

        total_height = assembly.total_thickness_in
        ax.set_xlim(0, x_offset + width + 8)
        ax.set_ylim(start_y - 2, start_y + total_height + 2)
        ax.set_aspect('equal')
        ax.axis('off')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        return {
            'figure': fig,
            'assembly': assembly,
            'r_value': r_total,
        }

    def render_assembly_comparison(
        self,
        assemblies: List[LayeredAssembly],
        show_thermal: bool = True,
        indoor_temp_f: float = 70,
        outdoor_temp_f: float = 10,
        save_path: str = None
    ) -> Dict:
        """
        Render multiple assemblies side-by-side for comparison.

        Args:
            assemblies: List of assemblies to compare
            show_thermal: Show temperature profiles
            indoor_temp_f: Indoor temperature
            outdoor_temp_f: Outdoor temperature
            save_path: Path to save image

        Returns:
            Dict with figure and comparison data
        """
        n = len(assemblies)
        fig, axes = plt.subplots(1, n, figsize=(6*n, 10), facecolor=self.bg_color)
        if n == 1:
            axes = [axes]

        comparison_data = []

        for i, (ax, assembly) in enumerate(zip(axes, assemblies)):
            ax.set_facecolor(self.bg_color)

            x_offset = 1.0
            start_y = 0.5
            width = 8.0

            # Draw layers
            current_y = start_y
            for layer in assembly.layers:
                self._draw_layer(ax, layer, x_offset, current_y, width, show_framing=False)
                current_y += layer.thickness_in

            # Title
            ax.set_title(assembly.name, fontsize=11, color=self.text_color, pad=10)

            # R-value label
            r_val = assembly.total_r_value
            ax.text(x_offset + width/2, start_y - 0.3, f'R-{r_val:.1f}',
                   ha='center', va='top', fontsize=12, color='#22c55e',
                   fontweight='bold')

            # Thickness
            total = assembly.total_thickness_in
            ax.text(x_offset + width/2, current_y + 0.2, f'{total:.1f}"',
                   ha='center', va='bottom', fontsize=10, color=self.dim_color)

            ax.set_xlim(0, width + 2)
            ax.set_ylim(-1, max(a.total_thickness_in for a in assemblies) + 2)
            ax.set_aspect('equal')
            ax.axis('off')

            comparison_data.append({
                'name': assembly.name,
                'r_value': r_val,
                'thickness': total,
                'u_factor': assembly.u_factor
            })

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        return {
            'figure': fig,
            'comparison': comparison_data
        }


    def render_wall_with_connections(
        self,
        assembly: LayeredAssembly,
        wall_height_ft: float = 8.0,
        section_width: float = 16.0,
        show_foundation: bool = True,
        show_plate_detail: bool = True,
        show_fastener_schedule: bool = True,
        show_thermal: bool = False,
        indoor_temp_f: float = 70,
        outdoor_temp_f: float = 20,
        save_path: str = None
    ) -> Dict:
        """
        Render a comprehensive wall section with structural connections
        and fastener schedule.

        Args:
            assembly: Wall assembly
            wall_height_ft: Wall height for context
            section_width: Width of section to show
            show_foundation: Show sill plate and anchor bolt
            show_plate_detail: Show top plate connection detail
            show_fastener_schedule: Include fastener count table
            show_thermal: Show temperature gradient
            save_path: Path to save

        Returns:
            Dict with figure and material takeoff
        """
        from .connections import (FastenerEstimator, ConnectionRenderer,
                                   Connector, Fastener)

        title = f"Wall Detail: {assembly.name}"
        fig = plt.figure(figsize=(20, 14), facecolor=self.bg_color)

        # Main section area
        ax_main = fig.add_axes([0.05, 0.15, 0.55, 0.75], facecolor=self.bg_color)
        ax_main.set_title(title, fontsize=14, fontweight='bold', color=self.text_color)

        x_offset = 4.0
        start_y = 2.0 if show_foundation else 1.0
        width = section_width

        # Draw foundation/sill if requested
        if show_foundation:
            # Concrete foundation
            foundation_height = 1.5
            foundation_rect = Rectangle((x_offset - 1, start_y - foundation_height - 0.5),
                                         width + 2, foundation_height,
                                         facecolor='#9ca3af', edgecolor=self.cut_line_color,
                                         linewidth=1.5)
            ax_main.add_patch(foundation_rect)
            HatchPatterns.create_concrete(ax_main, x_offset - 1, start_y - foundation_height - 0.5,
                                          width + 2, foundation_height)

            # Sill plate (pressure treated)
            sill_plate = Rectangle((x_offset, start_y - 0.5), width, 1.5,
                                    facecolor='#65a30d', edgecolor=self.cut_line_color,
                                    linewidth=1)
            ax_main.add_patch(sill_plate)
            ax_main.text(x_offset + width + 0.3, start_y + 0.25, 'PT Sill Plate',
                        ha='left', va='center', fontsize=8, color=self.text_color)

            # Anchor bolt
            conn_renderer = ConnectionRenderer(self.dark_mode)
            bolt_x = x_offset + width * 0.3
            conn_renderer.draw_anchor_bolt(ax_main, bolt_x, start_y - 0.5, scale=1.0)

            # Sill seal
            ax_main.fill_between([x_offset, x_offset + width],
                                 start_y - 0.52, start_y - 0.48,
                                 color='#fbbf24', alpha=0.7)
            ax_main.text(x_offset + width + 0.3, start_y - 0.5, 'Sill Seal',
                        ha='left', va='center', fontsize=7, color='#fbbf24')

        # Draw wall layers
        current_y = start_y
        for layer in assembly.layers:
            self._draw_layer(ax_main, layer, x_offset, current_y, width, show_framing=True)
            current_y += layer.thickness_in

        # Top plates
        if show_plate_detail:
            plate_y = current_y
            # Single top plate
            top_plate1 = Rectangle((x_offset, plate_y), width, 1.5,
                                    facecolor='#d6b88a', edgecolor=self.cut_line_color,
                                    linewidth=1)
            ax_main.add_patch(top_plate1)
            HatchPatterns.create_wood_grain(ax_main, x_offset, plate_y, width, 1.5,
                                            grain_type='face', density=0.12)

            # Double top plate
            plate_y += 1.5
            top_plate2 = Rectangle((x_offset, plate_y), width, 1.5,
                                    facecolor='#c9a86c', edgecolor=self.cut_line_color,
                                    linewidth=1)
            ax_main.add_patch(top_plate2)
            HatchPatterns.create_wood_grain(ax_main, x_offset, plate_y, width, 1.5,
                                            grain_type='face', density=0.12)

            ax_main.text(x_offset + width + 0.3, plate_y + 0.75, 'Double Top Plate',
                        ha='left', va='center', fontsize=8, color=self.text_color)

            current_y = plate_y + 1.5

        # Labels
        ax_main.text(x_offset + width/2, start_y - 1.2 if show_foundation else start_y - 0.5,
                    'INTERIOR', ha='center', va='top', fontsize=10,
                    color=self.text_color, fontweight='bold')
        ax_main.text(x_offset + width/2, current_y + 0.5,
                    'EXTERIOR', ha='center', va='bottom', fontsize=10,
                    color=self.text_color, fontweight='bold')

        # Dimensions
        self._draw_dimensions(ax_main, assembly, x_offset, start_y, dim_offset=1.5)

        # Callouts
        self._draw_callouts(ax_main, assembly, x_offset, width, start_y, callout_offset=0.8)

        # Thermal overlay
        if show_thermal:
            self._draw_thermal_overlay(ax_main, assembly, x_offset, width, start_y,
                                       indoor_temp_f, outdoor_temp_f, 40)

        # R-value box
        r_total = assembly.total_r_value
        u_factor = assembly.u_factor
        summary_text = f"R-Value: {r_total:.1f}\nU-Factor: {u_factor:.3f}"
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#22c55e', linewidth=2, alpha=0.9)
        ax_main.text(0.02, 0.98, summary_text, transform=ax_main.transAxes, fontsize=10,
                    verticalalignment='top', fontfamily='monospace',
                    color=self.text_color, bbox=props)

        total_height = assembly.total_thickness_in + (3.0 if show_plate_detail else 0)
        ax_main.set_xlim(0, x_offset + width + 6)
        ax_main.set_ylim(start_y - 3 if show_foundation else start_y - 1.5,
                         start_y + total_height + 1)
        ax_main.set_aspect('equal')
        ax_main.axis('off')

        # Fastener schedule panel
        if show_fastener_schedule:
            ax_schedule = fig.add_axes([0.62, 0.15, 0.35, 0.75], facecolor=self.bg_color)
            ax_schedule.axis('off')

            # Calculate fasteners for 8' wall section
            estimator = FastenerEstimator()
            schedule = estimator.estimate_wall_fasteners(
                wall_length_ft=section_width / 12,
                wall_height_ft=wall_height_ft,
                stud_spacing_in=16,
                has_sheathing=True,
                has_drywall=True,
                has_siding=True
            )

            # Title
            ax_schedule.text(0.5, 0.98, 'FASTENER SCHEDULE',
                           ha='center', va='top', fontsize=12, fontweight='bold',
                           color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.5, 0.94, f'(Per {section_width/12:.1f} ft wall section)',
                           ha='center', va='top', fontsize=9, color=self.dim_color,
                           transform=ax_schedule.transAxes)

            # Table content
            y_pos = 0.88
            line_height = 0.045

            # Framing section
            ax_schedule.text(0.05, y_pos, 'FRAMING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for location, count in schedule.framing_nails.items():
                ax_schedule.text(0.08, y_pos, f'{location.replace("_", " ").title()}:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{count} - 16d nails',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height / 2

            # Sheathing section
            ax_schedule.text(0.05, y_pos, 'SHEATHING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for location, count in schedule.sheathing_nails.items():
                ax_schedule.text(0.08, y_pos, f'{location.title()} nailing:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{count} - 8d nails',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height / 2

            # Finishes section
            ax_schedule.text(0.05, y_pos, 'FINISHES', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Drywall:',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, f'{schedule.drywall_screws} screws',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Siding:',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, f'{schedule.siding_fasteners} nails',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 1.5

            # Connectors section
            ax_schedule.text(0.05, y_pos, 'CONNECTORS', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            if show_foundation:
                ax_schedule.text(0.08, y_pos, 'Anchor bolts:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                num_anchors = max(1, int(section_width / 12 / 6) + 1)  # 6' OC
                ax_schedule.text(0.7, y_pos, f'{num_anchors} - 1/2"x10" J-bolt',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Hold-downs (if shear wall):',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, '2 - HDU5',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 2

            # Total estimate - draw line manually since axhline doesn't support transform
            ax_schedule.plot([0.05, 0.75], [y_pos + line_height/2, y_pos + line_height/2],
                            color=self.dim_color, linewidth=0.5,
                            transform=ax_schedule.transAxes)

            total_16d = sum(schedule.framing_nails.values())
            total_8d = sum(schedule.sheathing_nails.values())

            ax_schedule.text(0.05, y_pos, 'TOTALS', fontsize=10, fontweight='bold',
                           color='#22c55e', transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, f'16d nails: {total_16d} ({total_16d/47:.1f} lbs)',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'8d nails: {total_8d} ({total_8d/99:.1f} lbs)',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'Drywall screws: {schedule.drywall_screws}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'Siding fasteners: {schedule.siding_fasteners}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)

            # Nailing schedule note
            y_pos -= line_height * 2
            ax_schedule.text(0.05, y_pos, 'NAILING SCHEDULE NOTES:',
                           fontsize=8, fontweight='bold', color=self.dim_color,
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 0.8
            notes = [
                '• Sheathing edge: 6" OC (3" high wind/seismic)',
                '• Sheathing field: 12" OC at studs',
                '• Drywall edge: 8" OC, field: 12" OC',
                '• Stud to plate: 2-16d end nailed or 4-8d toenailed',
            ]
            for note in notes:
                ax_schedule.text(0.05, y_pos, note, fontsize=7, color=self.dim_color,
                               transform=ax_schedule.transAxes)
                y_pos -= line_height * 0.7

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        # Build material takeoff
        takeoff = {
            'assembly': assembly.name,
            'r_value': r_total,
            'u_factor': u_factor,
            'thickness_in': assembly.total_thickness_in,
        }

        if show_fastener_schedule:
            takeoff['fasteners'] = {
                '16d_nails': sum(schedule.framing_nails.values()),
                '8d_nails': sum(schedule.sheathing_nails.values()),
                'drywall_screws': schedule.drywall_screws,
                'siding_nails': schedule.siding_fasteners,
            }

        return {
            'figure': fig,
            'takeoff': takeoff
        }

    def render_floor_with_connections(
        self,
        assembly: LayeredAssembly,
        floor_span_ft: float = 12.0,
        section_width: float = 32.0,
        show_rim_board: bool = True,
        show_joist_hangers: bool = True,
        show_fastener_schedule: bool = True,
        save_path: str = None
    ) -> Dict:
        """
        Render a comprehensive floor section with structural connections
        and fastener schedule.

        Args:
            assembly: Floor assembly
            floor_span_ft: Floor span for context
            section_width: Width of section to show
            show_rim_board: Show rim/band joist at end
            show_joist_hangers: Show joist hanger connectors
            show_fastener_schedule: Include fastener count table
            save_path: Path to save

        Returns:
            Dict with figure and material takeoff
        """
        from .connections import (FastenerEstimator, ConnectionRenderer, Connector)

        title = f"Floor Detail: {assembly.name}"
        fig = plt.figure(figsize=(22, 12), facecolor=self.bg_color)

        # Main section area
        ax_main = fig.add_axes([0.05, 0.15, 0.55, 0.75], facecolor=self.bg_color)
        ax_main.set_title(title, fontsize=14, fontweight='bold', color=self.text_color)

        x_offset = 3.0
        start_y = 2.0
        width = section_width

        conn_renderer = ConnectionRenderer(self.dark_mode)

        # Draw bearing wall/rim on left side
        if show_rim_board:
            # Supporting wall top plates
            wall_plate = Rectangle((x_offset - 3, start_y - 1.5), 3, 3,
                                    facecolor='#d6b88a', edgecolor=self.cut_line_color,
                                    linewidth=1.5)
            ax_main.add_patch(wall_plate)
            HatchPatterns.create_wood_grain(ax_main, x_offset - 3, start_y - 1.5, 3, 3,
                                            grain_type='end')
            ax_main.text(x_offset - 1.5, start_y, 'Top Plates',
                        ha='center', va='center', fontsize=7, color=self.text_color,
                        rotation=90)

            # Rim/band joist
            rim_width = 1.5
            rim_height = assembly.total_thickness_in - 1.5  # Minus subfloor/finish
            rim = Rectangle((x_offset, start_y), rim_width, rim_height,
                            facecolor='#c9a86c', edgecolor=self.cut_line_color,
                            linewidth=1.5)
            ax_main.add_patch(rim)
            HatchPatterns.create_wood_grain(ax_main, x_offset, start_y, rim_width, rim_height,
                                            grain_type='face')
            ax_main.text(x_offset + width + 1.5, start_y + rim_height/2, 'Rim Board (1-3/4" LVL)',
                        ha='left', va='center', fontsize=8, color=self.text_color)

        # Draw floor layers
        current_y = start_y
        joist_y = None
        for layer in assembly.layers:
            # Skip drawing joist cavity as full layer - we'll draw joists separately
            if layer.is_framing_layer and layer.thickness_in > 5:
                joist_y = current_y
                joist_depth = layer.thickness_in
                # Draw joist cavity (air space)
                rect = Rectangle((x_offset + 2 if show_rim_board else x_offset, current_y),
                                 width - (2 if show_rim_board else 0), layer.thickness_in,
                                 facecolor='#374151' if self.dark_mode else '#f8fafc',
                                 edgecolor=self.cut_line_color, linewidth=1)
                ax_main.add_patch(rect)

                # Draw individual joists
                joist_spacing = layer.framing_spacing_in
                num_joists = int((width - 4) / joist_spacing) + 1
                for i in range(num_joists):
                    joist_x = x_offset + 3 + i * joist_spacing
                    if joist_x < x_offset + width - 2:
                        # I-joist or dimensional lumber
                        joist_width = layer.framing_width_in if layer.framing_width_in else 1.5

                        if 'tji' in assembly.name.lower() or 'i-joist' in assembly.name.lower():
                            # Draw I-joist shape
                            flange_h = 1.5
                            web_w = 0.375

                            # Top flange
                            top_flange = Rectangle((joist_x - joist_width/2, current_y + joist_depth - flange_h),
                                                   joist_width, flange_h,
                                                   facecolor='#a16207', edgecolor='#78350f', linewidth=0.5)
                            ax_main.add_patch(top_flange)

                            # Web
                            web = Rectangle((joist_x - web_w/2, current_y + flange_h),
                                           web_w, joist_depth - 2*flange_h,
                                           facecolor='#c9a86c', edgecolor='#78350f', linewidth=0.5)
                            ax_main.add_patch(web)

                            # Bottom flange
                            bot_flange = Rectangle((joist_x - joist_width/2, current_y),
                                                   joist_width, flange_h,
                                                   facecolor='#a16207', edgecolor='#78350f', linewidth=0.5)
                            ax_main.add_patch(bot_flange)
                        else:
                            # Solid lumber joist
                            joist_rect = Rectangle((joist_x - joist_width/2, current_y),
                                                   joist_width, joist_depth,
                                                   facecolor='#c9a86c', edgecolor='#78350f', linewidth=0.5)
                            ax_main.add_patch(joist_rect)
                            HatchPatterns.create_wood_grain(ax_main, joist_x - joist_width/2, current_y,
                                                           joist_width, joist_depth, grain_type='face')

                        # Draw joist hanger at rim
                        if show_joist_hangers and i == 0:
                            hanger = Connector.lus210()
                            conn_renderer.draw_joist_hanger(ax_main, joist_x, current_y, hanger, scale=1.0)

            else:
                self._draw_layer(ax_main, layer, x_offset, current_y, width, show_framing=False)

            current_y += layer.thickness_in

        # Labels
        ax_main.text(x_offset + width/2, start_y - 0.5, 'BOTTOM (Ceiling below)',
                    ha='center', va='top', fontsize=10, color=self.text_color, fontweight='bold')
        ax_main.text(x_offset + width/2, current_y + 0.5, 'TOP (Finish Floor)',
                    ha='center', va='bottom', fontsize=10, color=self.text_color, fontweight='bold')

        # Dimensions
        self._draw_dimensions(ax_main, assembly, x_offset, start_y, dim_offset=1.0)

        # Callouts
        callout_y = start_y
        for layer in assembly.layers:
            mid_y = callout_y + layer.thickness_in / 2
            if layer.thickness_in >= 0.3:
                ax_main.plot([x_offset + width, x_offset + width + 1.0], [mid_y, mid_y],
                            color=self.dim_color, linewidth=0.5)
                ax_main.text(x_offset + width + 1.1, mid_y, layer.material.name,
                            ha='left', va='center', fontsize=8, color=self.text_color)
            callout_y += layer.thickness_in

        # Summary box
        total_depth = assembly.total_thickness_in
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#6366f1', linewidth=2, alpha=0.9)
        ax_main.text(0.02, 0.98, f"Total Depth: {total_depth:.2f}\"",
                    transform=ax_main.transAxes, fontsize=10, verticalalignment='top',
                    fontfamily='monospace', color=self.text_color, bbox=props)

        ax_main.set_xlim(-1, x_offset + width + 8)
        ax_main.set_ylim(start_y - 3, current_y + 2)
        ax_main.set_aspect('equal')
        ax_main.axis('off')

        # Fastener schedule panel
        if show_fastener_schedule:
            ax_schedule = fig.add_axes([0.62, 0.15, 0.35, 0.75], facecolor=self.bg_color)
            ax_schedule.axis('off')

            estimator = FastenerEstimator()
            schedule = estimator.estimate_floor_fasteners(
                floor_length_ft=section_width / 12,
                floor_width_ft=floor_span_ft,
                joist_spacing_in=16
            )

            # Title
            ax_schedule.text(0.5, 0.98, 'FASTENER SCHEDULE',
                           ha='center', va='top', fontsize=12, fontweight='bold',
                           color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.5, 0.94, f'(Per {section_width/12:.1f} ft floor section)',
                           ha='center', va='top', fontsize=9, color=self.dim_color,
                           transform=ax_schedule.transAxes)

            y_pos = 0.88
            line_height = 0.045

            # Framing
            ax_schedule.text(0.05, y_pos, 'FRAMING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for location, count in schedule.framing_nails.items():
                ax_schedule.text(0.08, y_pos, f'{location.replace("_", " ").title()}:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{count} - 16d nails',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height / 2

            # Subfloor
            ax_schedule.text(0.05, y_pos, 'SUBFLOOR', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Subfloor fasteners:',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, f'{schedule.subfloor_fasteners} - 8d ring shank',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Construction adhesive:',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, 'Continuous bead on joists',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 1.5

            # Connectors
            ax_schedule.text(0.05, y_pos, 'CONNECTORS', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for connector, qty in schedule.connectors:
                ax_schedule.text(0.08, y_pos, f'{connector.model}:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{qty} units',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height

            # Totals
            ax_schedule.plot([0.05, 0.75], [y_pos + line_height/2, y_pos + line_height/2],
                            color=self.dim_color, linewidth=0.5, transform=ax_schedule.transAxes)

            ax_schedule.text(0.05, y_pos, 'TOTALS', fontsize=10, fontweight='bold',
                           color='#22c55e', transform=ax_schedule.transAxes)
            y_pos -= line_height

            total_framing = sum(schedule.framing_nails.values())
            ax_schedule.text(0.08, y_pos, f'16d nails: {total_framing} ({total_framing/47:.1f} lbs)',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'Subfloor nails: {schedule.subfloor_fasteners}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height

            connector_cost = sum(c.unit_cost * q for c, q in schedule.connectors)
            ax_schedule.text(0.08, y_pos, f'Connector cost: ${connector_cost:.2f}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)

            # Notes
            y_pos -= line_height * 2
            ax_schedule.text(0.05, y_pos, 'FLOOR FRAMING NOTES:',
                           fontsize=8, fontweight='bold', color=self.dim_color,
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 0.8
            notes = [
                '• Subfloor: 6" OC edge, 12" OC field',
                '• Glue + nail for squeak-free floor',
                '• Joist hangers per manufacturer specs',
                '• Block at 8\' OC for spans >12\'',
            ]
            for note in notes:
                ax_schedule.text(0.05, y_pos, note, fontsize=7, color=self.dim_color,
                               transform=ax_schedule.transAxes)
                y_pos -= line_height * 0.7

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        takeoff = {
            'assembly': assembly.name,
            'total_depth_in': assembly.total_thickness_in,
        }
        if show_fastener_schedule:
            takeoff['fasteners'] = {
                '16d_nails': sum(schedule.framing_nails.values()),
                'subfloor_nails': schedule.subfloor_fasteners,
                'joist_hangers': sum(q for _, q in schedule.connectors),
            }

        return {'figure': fig, 'takeoff': takeoff}

    def render_roof_with_connections(
        self,
        assembly: LayeredAssembly,
        roof_span_ft: float = 24.0,
        section_width: float = 32.0,
        roof_pitch: float = 6.0,  # 6:12
        show_ridge: bool = True,
        show_bird_block: bool = True,
        show_hurricane_ties: bool = True,
        show_fastener_schedule: bool = True,
        save_path: str = None
    ) -> Dict:
        """
        Render a comprehensive roof section with structural connections
        and fastener schedule.

        Args:
            assembly: Roof assembly
            roof_span_ft: Roof span
            section_width: Width of section to show
            roof_pitch: Pitch (rise per 12" run)
            show_ridge: Show ridge board/beam
            show_bird_block: Show bird blocking at eave
            show_hurricane_ties: Show hurricane tie connectors
            show_fastener_schedule: Include fastener count table
            save_path: Path to save

        Returns:
            Dict with figure and material takeoff
        """
        from .connections import (FastenerEstimator, ConnectionRenderer, Connector)

        title = f"Roof Detail: {assembly.name}"
        fig = plt.figure(figsize=(22, 14), facecolor=self.bg_color)

        ax_main = fig.add_axes([0.05, 0.15, 0.55, 0.75], facecolor=self.bg_color)
        ax_main.set_title(title, fontsize=14, fontweight='bold', color=self.text_color)

        x_offset = 4.0
        start_y = 3.0
        width = section_width

        conn_renderer = ConnectionRenderer(self.dark_mode)

        # Top plate (bearing)
        plate_rect = Rectangle((x_offset - 2, start_y - 3), width + 4, 3,
                                facecolor='#d6b88a', edgecolor=self.cut_line_color,
                                linewidth=1.5)
        ax_main.add_patch(plate_rect)
        HatchPatterns.create_wood_grain(ax_main, x_offset - 2, start_y - 3, width + 4, 3,
                                        grain_type='face')
        ax_main.text(x_offset - 3, start_y - 1.5, 'Double\nTop Plate',
                    ha='right', va='center', fontsize=8, color=self.text_color)

        # Draw roof layers
        current_y = start_y
        rafter_y = None
        rafter_depth = 0

        for layer in assembly.layers:
            if layer.is_framing_layer and layer.thickness_in > 3:
                rafter_y = current_y
                rafter_depth = layer.thickness_in

                # Rafter cavity
                rect = Rectangle((x_offset, current_y), width, layer.thickness_in,
                                 facecolor='#374151' if self.dark_mode else '#f8fafc',
                                 edgecolor=self.cut_line_color, linewidth=1)
                ax_main.add_patch(rect)

                # Draw rafters/trusses
                rafter_spacing = layer.framing_spacing_in if layer.framing_spacing_in else 24
                num_rafters = int(width / rafter_spacing) + 1
                rafter_width = layer.framing_width_in if layer.framing_width_in else 1.5

                for i in range(num_rafters):
                    rafter_x = x_offset + 2 + i * rafter_spacing
                    if rafter_x < x_offset + width - 2:
                        rafter_rect = Rectangle((rafter_x - rafter_width/2, current_y),
                                               rafter_width, rafter_depth,
                                               facecolor='#c9a86c', edgecolor='#78350f',
                                               linewidth=0.5)
                        ax_main.add_patch(rafter_rect)
                        HatchPatterns.create_wood_grain(ax_main, rafter_x - rafter_width/2,
                                                       current_y, rafter_width, rafter_depth,
                                                       grain_type='face')

                        # Hurricane tie at plate
                        if show_hurricane_ties and i < 3:
                            tie = Connector.h2_5()
                            conn_renderer.draw_hurricane_tie(ax_main, rafter_x, start_y,
                                                            tie, scale=0.8,
                                                            orientation='right' if i % 2 == 0 else 'left')
            else:
                self._draw_layer(ax_main, layer, x_offset, current_y, width, show_framing=False)

            current_y += layer.thickness_in

        # Bird blocking at eave
        if show_bird_block and rafter_y is not None:
            block_x = x_offset
            block_rect = Rectangle((block_x, rafter_y), 3.5, rafter_depth * 0.6,
                                   facecolor='#b8956e', edgecolor='#78350f', linewidth=1)
            ax_main.add_patch(block_rect)
            ax_main.text(block_x + 1.75, rafter_y + rafter_depth * 0.3, 'Bird\nBlock',
                        ha='center', va='center', fontsize=6, color='#1f2937')

        # Ridge (simplified - at right edge)
        if show_ridge:
            ridge_x = x_offset + width - 2
            ridge_rect = Rectangle((ridge_x, rafter_y), 1.5, rafter_depth,
                                   facecolor='#a16207', edgecolor='#78350f', linewidth=1.5)
            ax_main.add_patch(ridge_rect)
            ax_main.text(ridge_x + 0.75, rafter_y + rafter_depth + 0.5, 'Ridge Board',
                        ha='center', va='bottom', fontsize=8, color=self.text_color)

        # Labels
        ax_main.text(x_offset + width/2, start_y - 4, 'INTERIOR (Ceiling)',
                    ha='center', va='top', fontsize=10, color=self.text_color, fontweight='bold')
        ax_main.text(x_offset + width/2, current_y + 0.5, 'EXTERIOR (Roof Surface)',
                    ha='center', va='bottom', fontsize=10, color=self.text_color, fontweight='bold')

        # Dimensions
        self._draw_dimensions(ax_main, assembly, x_offset, start_y, dim_offset=1.5)

        # Pitch indicator
        pitch_angle = np.arctan(roof_pitch / 12) * 180 / np.pi
        ax_main.text(x_offset + width + 2, current_y - 1,
                    f'Pitch: {roof_pitch:.0f}:12\n({pitch_angle:.1f}°)',
                    ha='left', va='center', fontsize=9, color=self.dim_color)

        # R-value box
        r_total = assembly.total_r_value
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor='#f59e0b', linewidth=2, alpha=0.9)
        ax_main.text(0.02, 0.98, f"R-Value: {r_total:.1f}",
                    transform=ax_main.transAxes, fontsize=10, verticalalignment='top',
                    fontfamily='monospace', color=self.text_color, bbox=props)

        ax_main.set_xlim(-2, x_offset + width + 8)
        ax_main.set_ylim(start_y - 5, current_y + 3)
        ax_main.set_aspect('equal')
        ax_main.axis('off')

        # Fastener schedule
        if show_fastener_schedule:
            ax_schedule = fig.add_axes([0.62, 0.15, 0.35, 0.75], facecolor=self.bg_color)
            ax_schedule.axis('off')

            estimator = FastenerEstimator()
            schedule = estimator.estimate_roof_fasteners(
                roof_length_ft=section_width / 12,
                roof_width_ft=roof_span_ft / 2,  # Half span (one side)
                rafter_spacing_in=24,
                has_sheathing=True,
                has_shingles=True,
                hurricane_ties=show_hurricane_ties
            )

            ax_schedule.text(0.5, 0.98, 'FASTENER SCHEDULE',
                           ha='center', va='top', fontsize=12, fontweight='bold',
                           color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.5, 0.94, f'(Per {section_width/12:.1f} ft roof section)',
                           ha='center', va='top', fontsize=9, color=self.dim_color,
                           transform=ax_schedule.transAxes)

            y_pos = 0.88
            line_height = 0.045

            # Framing
            ax_schedule.text(0.05, y_pos, 'FRAMING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for location, count in schedule.framing_nails.items():
                ax_schedule.text(0.08, y_pos, f'{location.replace("_", " ").title()}:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{count} - 16d nails',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height / 2

            # Sheathing
            ax_schedule.text(0.05, y_pos, 'SHEATHING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for location, count in schedule.sheathing_nails.items():
                ax_schedule.text(0.08, y_pos, f'{location.title()} nailing:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{count} - 8d nails',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height / 2

            # Roofing
            ax_schedule.text(0.05, y_pos, 'ROOFING', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            ax_schedule.text(0.08, y_pos, 'Shingle nails:',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            ax_schedule.text(0.7, y_pos, f'{schedule.roofing_fasteners} - roofing nails',
                           fontsize=9, color=self.dim_color, ha='right',
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 1.5

            # Connectors
            ax_schedule.text(0.05, y_pos, 'CONNECTORS', fontsize=10, fontweight='bold',
                           color='#f59e0b', transform=ax_schedule.transAxes)
            y_pos -= line_height

            for connector, qty in schedule.connectors:
                ax_schedule.text(0.08, y_pos, f'{connector.model} Hurricane Ties:',
                               fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
                ax_schedule.text(0.7, y_pos, f'{qty} units',
                               fontsize=9, color=self.dim_color, ha='right',
                               transform=ax_schedule.transAxes)
                y_pos -= line_height

            y_pos -= line_height

            # Totals
            ax_schedule.plot([0.05, 0.75], [y_pos + line_height/2, y_pos + line_height/2],
                            color=self.dim_color, linewidth=0.5, transform=ax_schedule.transAxes)

            ax_schedule.text(0.05, y_pos, 'TOTALS', fontsize=10, fontweight='bold',
                           color='#22c55e', transform=ax_schedule.transAxes)
            y_pos -= line_height

            total_framing = sum(schedule.framing_nails.values())
            total_sheathing = sum(schedule.sheathing_nails.values())

            ax_schedule.text(0.08, y_pos, f'16d nails: {total_framing}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'8d sheathing nails: {total_sheathing}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)
            y_pos -= line_height
            ax_schedule.text(0.08, y_pos, f'Roofing nails: {schedule.roofing_fasteners}',
                           fontsize=9, color=self.text_color, transform=ax_schedule.transAxes)

            # Notes
            y_pos -= line_height * 2
            ax_schedule.text(0.05, y_pos, 'ROOF FRAMING NOTES:',
                           fontsize=8, fontweight='bold', color=self.dim_color,
                           transform=ax_schedule.transAxes)
            y_pos -= line_height * 0.8
            notes = [
                '• Sheathing: H-clips at unsupported edges',
                '• Shingles: 4 nails per shingle min',
                '• 6 nails per shingle in high wind zone',
                '• Hurricane ties at each rafter/truss',
            ]
            for note in notes:
                ax_schedule.text(0.05, y_pos, note, fontsize=7, color=self.dim_color,
                               transform=ax_schedule.transAxes)
                y_pos -= line_height * 0.7

        if save_path:
            plt.savefig(save_path, dpi=200, facecolor=self.bg_color,
                       edgecolor='none', bbox_inches='tight')

        takeoff = {
            'assembly': assembly.name,
            'r_value': r_total,
            'pitch': f'{roof_pitch}:12',
        }
        if show_fastener_schedule:
            takeoff['fasteners'] = {
                '16d_nails': sum(schedule.framing_nails.values()),
                '8d_nails': sum(schedule.sheathing_nails.values()),
                'roofing_nails': schedule.roofing_fasteners,
                'hurricane_ties': sum(q for _, q in schedule.connectors),
            }

        return {'figure': fig, 'takeoff': takeoff}


# Quick test
if __name__ == "__main__":
    from assemblies import LayeredAssembly

    renderer = DetailRenderer(dark_mode=True)

    print("Rendering wall section detail...")
    wall = LayeredAssembly.wall_2x6_r21_plus_ci()
    result = renderer.render_wall_section(
        wall,
        show_thermal=True,
        indoor_temp_f=70,
        outdoor_temp_f=10,
        indoor_rh_pct=45,
        save_path="detail_wall_section.png"
    )
    print(f"Wall R-value: {result['r_value']:.1f}")

    print("\nRendering floor section detail...")
    floor = LayeredAssembly.floor_tji_14()
    result = renderer.render_floor_section(
        floor,
        save_path="detail_floor_section.png"
    )
    print(f"Floor depth: {result['total_depth']:.1f}\"")

    print("\nRendering roof section detail...")
    roof = LayeredAssembly.roof_unvented_cathedral()
    result = renderer.render_roof_section(
        roof,
        save_path="detail_roof_section.png"
    )
    print(f"Roof R-value: {result['r_value']:.1f}")

    print("\nRendering comparison...")
    walls = [
        LayeredAssembly.wall_2x4_r13(),
        LayeredAssembly.wall_2x6_r21(),
        LayeredAssembly.wall_2x6_r21_plus_ci(),
        LayeredAssembly.wall_double_stud(),
    ]
    result = renderer.render_assembly_comparison(
        walls,
        save_path="detail_wall_comparison.png"
    )

    print("\nDetails rendered!")
    plt.show()
