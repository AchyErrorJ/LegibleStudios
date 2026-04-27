# structural_viz.py
# Structural visualization - stress colors, deflection, failure modes
#
# Phase 1: Matplotlib static/animated visualizations
# Phase 2: Real-time WebGL/OpenGL renderer

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import math

from .structural import StructuralAnalyzer, Material, BeamResult, ColumnResult


# Stress colormap: green (safe) -> yellow (warning) -> red (failure)
STRESS_COLORS = LinearSegmentedColormap.from_list(
    'stress', ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444']
)


@dataclass
class VisualBeam:
    """Beam data for visualization"""
    span_ft: float
    width_in: float
    depth_in: float
    material: Material
    uniform_load_plf: float
    point_loads: List[Tuple[float, float]] = None
    result: BeamResult = None


@dataclass
class VisualColumn:
    """Column data for visualization"""
    height_ft: float
    width_in: float
    depth_in: float
    material: Material
    axial_load_lbs: float
    result: ColumnResult = None


class StructuralVisualizer:
    """
    Visualize structural analysis results.
    Shows stress distribution, deflection, and failure modes.
    """

    def __init__(self, dark_mode: bool = True):
        self.analyzer = StructuralAnalyzer()
        self.dark_mode = dark_mode

        if dark_mode:
            self.bg_color = '#1a1a2e'
            self.text_color = '#eeeeff'
            self.grid_color = '#333355'
            self.member_color = '#4a4a6a'
        else:
            self.bg_color = '#ffffff'
            self.text_color = '#222222'
            self.grid_color = '#cccccc'
            self.member_color = '#888888'

    def _setup_figure(self, figsize=(12, 6), title=""):
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

    def visualize_beam(
        self,
        span_ft: float,
        width_in: float,
        depth_in: float,
        material: Material,
        uniform_load_plf: float,
        point_loads: List[Tuple[float, float]] = None,
        show_loads: bool = True,
        show_stress: bool = True,
        show_deflection: bool = True,
        deflection_scale: float = 50.0,
        save_path: str = None
    ) -> Dict:
        """
        Visualize a beam with stress distribution and deflected shape.

        Args:
            span_ft: Beam span in feet
            width_in, depth_in: Cross section dimensions
            material: Beam material
            uniform_load_plf: Uniform load (lb/ft)
            point_loads: Optional point loads [(position_ft, load_lbs), ...]
            show_loads: Draw load arrows
            show_stress: Color beam by stress level
            show_deflection: Show deflected shape
            deflection_scale: Exaggeration factor for deflection
            save_path: Optional path to save image

        Returns:
            Dict with analysis results and figure
        """
        # Run analysis
        result = self.analyzer.analyze_simple_beam(
            span_ft, width_in, depth_in, material, uniform_load_plf, point_loads
        )

        fig, ax = self._setup_figure(figsize=(14, 8), title=f"Beam Analysis: {span_ft}ft span, {width_in}×{depth_in}in {material.name}")

        # Calculate deflection curve
        span_in = span_ft * 12
        n_points = 100
        x = np.linspace(0, span_in, n_points)

        # Deflection formula: δ(x) = (w*x*(L³ - 2Lx² + x³)) / (24EI)
        w = uniform_load_plf / 12  # lb/in
        L = span_in
        E = material.elastic_modulus_psi
        I = (width_in * depth_in**3) / 12

        deflection = (w * x * (L**3 - 2*L*x**2 + x**3)) / (24 * E * I)

        # Scale for visibility
        max_deflection = max(abs(deflection))
        if max_deflection > 0:
            visual_deflection = deflection * deflection_scale * (depth_in / max_deflection) * 0.5
        else:
            visual_deflection = deflection

        # Convert to feet for display
        x_ft = x / 12

        # Draw undeformed beam (gray)
        beam_y = depth_in / 2
        ax.fill_between(x_ft, 0, depth_in, color=self.member_color, alpha=0.3, label='Undeformed')

        # Draw deflected beam with stress coloring
        if show_deflection and show_stress:
            # Calculate stress along beam (simplified - max at midspan)
            # Actual stress varies with moment diagram
            moment = np.zeros_like(x)
            for i, xi in enumerate(x):
                # Moment at position x for uniform load: M(x) = (w*x/2)*(L-x)
                moment[i] = (w * xi / 2) * (L - xi)

            stress = moment / ((width_in * depth_in**2) / 6)  # sigma = M/S
            utilization = stress / (material.yield_strength_psi / self.analyzer.safety_factor)
            utilization = np.clip(utilization, 0, 1.5)  # Cap at 150% for coloring

            # Create colored segments
            points = np.array([x_ft, beam_y - visual_deflection]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            norm = plt.Normalize(0, 1.2)
            lc = LineCollection(segments, cmap=STRESS_COLORS, norm=norm, linewidth=depth_in*0.8)
            lc.set_array(utilization[:-1])
            ax.add_collection(lc)

            # Add colorbar
            sm = plt.cm.ScalarMappable(cmap=STRESS_COLORS, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
            cbar.set_label('Utilization Ratio', color=self.text_color)
            cbar.ax.yaxis.set_tick_params(color=self.text_color)
            cbar.outline.set_edgecolor(self.grid_color)
            plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        elif show_deflection:
            # Just show deflected shape
            color = '#ef4444' if not result.passes else '#22c55e'
            ax.plot(x_ft, beam_y - visual_deflection, color=color, linewidth=3, label='Deflected')

        # Draw supports (triangles)
        support_size = depth_in * 0.4
        left_support = patches.RegularPolygon((0, -support_size/2), 3, radius=support_size/2,
                                               color='#6366f1', ec='white', linewidth=2)
        right_support = patches.RegularPolygon((span_ft, -support_size/2), 3, radius=support_size/2,
                                                color='#6366f1', ec='white', linewidth=2)
        ax.add_patch(left_support)
        ax.add_patch(right_support)

        # Draw loads
        if show_loads:
            # Uniform load arrows
            arrow_spacing = span_ft / 10
            for i in range(11):
                x_pos = i * arrow_spacing
                arrow_len = depth_in * 1.5
                ax.annotate('', xy=(x_pos, depth_in * 1.2),
                           xytext=(x_pos, depth_in * 1.2 + arrow_len),
                           arrowprops=dict(arrowstyle='->', color='#f97316', lw=2))

            # Load label
            ax.text(span_ft/2, depth_in * 2.5, f'{uniform_load_plf} lb/ft',
                   ha='center', color='#f97316', fontsize=12, fontweight='bold')

            # Point loads
            if point_loads:
                for pos_ft, load_lbs in point_loads:
                    ax.annotate('', xy=(pos_ft, depth_in * 1.2),
                               xytext=(pos_ft, depth_in * 3),
                               arrowprops=dict(arrowstyle='->', color='#ef4444', lw=3))
                    ax.text(pos_ft, depth_in * 3.2, f'{load_lbs} lb',
                           ha='center', color='#ef4444', fontsize=11, fontweight='bold')

        # Draw deflection annotation
        if show_deflection:
            mid_x = span_ft / 2
            mid_deflection = visual_deflection[n_points//2]
            actual_deflection = result.max_deflection_in

            ax.annotate(f'δ = {actual_deflection:.3f}"',
                       xy=(mid_x, beam_y - mid_deflection),
                       xytext=(mid_x + span_ft*0.2, beam_y - mid_deflection - depth_in),
                       color=self.text_color,
                       fontsize=11,
                       arrowprops=dict(arrowstyle='->', color=self.text_color, lw=1))

        # Results text box
        status = "✓ PASS" if result.passes else "✗ FAIL"
        status_color = '#22c55e' if result.passes else '#ef4444'

        results_text = f"""
{status}
Utilization: {result.utilization_ratio:.0%}
Max Stress: {result.max_stress_psi:.0f} / {result.allowable_stress_psi:.0f} psi
Deflection: {result.max_deflection_in:.3f}" / {result.allowable_deflection_in:.3f}"
"""

        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor=status_color, linewidth=2)
        ax.text(0.02, 0.98, results_text.strip(), transform=ax.transAxes, fontsize=10,
               verticalalignment='top', fontfamily='monospace',
               color=self.text_color, bbox=props)

        # Warnings
        if result.warnings:
            warning_text = '\n'.join([f'⚠ {w}' for w in result.warnings])
            ax.text(0.98, 0.02, warning_text, transform=ax.transAxes, fontsize=9,
                   verticalalignment='bottom', horizontalalignment='right',
                   color='#f97316', fontfamily='monospace')

        ax.set_xlim(-span_ft*0.1, span_ft*1.15)
        ax.set_ylim(-depth_in*2, depth_in*4)
        ax.set_xlabel('Position (ft)')
        ax.set_ylabel('Depth (in)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, color=self.grid_color)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color, edgecolor='none')

        return {
            'result': result,
            'figure': fig,
            'deflection_curve': (x_ft, deflection)
        }

    def visualize_beam_failure(
        self,
        span_ft: float,
        width_in: float,
        depth_in: float,
        material: Material,
        uniform_load_plf: float,
        frames: int = 60,
        save_path: str = None
    ) -> animation.FuncAnimation:
        """
        Animate beam failure - progressive deflection to collapse.

        Args:
            span_ft, width_in, depth_in: Beam geometry
            material: Beam material
            uniform_load_plf: Starting load
            frames: Animation frames
            save_path: Optional path to save animation (gif/mp4)

        Returns:
            matplotlib animation object
        """
        fig, ax = self._setup_figure(figsize=(14, 8), title="Beam Failure Animation")

        span_in = span_ft * 12
        n_points = 100
        x = np.linspace(0, span_in, n_points)
        x_ft = x / 12

        L = span_in
        E = material.elastic_modulus_psi
        I = (width_in * depth_in**3) / 12

        # Calculate failure load (when utilization = 1.0)
        result = self.analyzer.analyze_simple_beam(
            span_ft, width_in, depth_in, material, uniform_load_plf
        )
        failure_load = uniform_load_plf / result.utilization_ratio if result.utilization_ratio > 0 else uniform_load_plf * 2

        # We'll animate from 0 to 150% of failure load
        max_load = failure_load * 1.5

        # Initialize plot elements
        beam_line, = ax.plot([], [], color='#22c55e', linewidth=depth_in*0.5, solid_capstyle='round')
        load_text = ax.text(span_ft/2, depth_in*3, '', ha='center', color='#f97316', fontsize=14, fontweight='bold')
        status_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, fontsize=12,
                             verticalalignment='top', fontfamily='monospace', color=self.text_color)

        # Draw supports
        support_size = depth_in * 0.4
        left_support = patches.RegularPolygon((0, -support_size/2), 3, radius=support_size/2,
                                               color='#6366f1', ec='white', linewidth=2)
        right_support = patches.RegularPolygon((span_ft, -support_size/2), 3, radius=support_size/2,
                                                color='#6366f1', ec='white', linewidth=2)
        ax.add_patch(left_support)
        ax.add_patch(right_support)

        # Undeformed reference
        ax.fill_between(x_ft, 0, depth_in, color=self.member_color, alpha=0.2)
        ax.axhline(y=depth_in/2, color=self.grid_color, linestyle='--', alpha=0.5, label='Undeformed')

        ax.set_xlim(-span_ft*0.1, span_ft*1.1)
        ax.set_ylim(-depth_in*4, depth_in*4)
        ax.set_xlabel('Position (ft)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, color=self.grid_color)

        def init():
            beam_line.set_data([], [])
            load_text.set_text('')
            status_text.set_text('')
            return beam_line, load_text, status_text

        def animate(frame):
            # Progress from 0 to max_load
            progress = frame / frames
            current_load = progress * max_load

            if current_load < 1:
                current_load = 1  # Avoid division issues

            # Calculate deflection
            w = current_load / 12
            deflection = (w * x * (L**3 - 2*L*x**2 + x**3)) / (24 * E * I)

            # Calculate utilization
            M_max = (current_load / 12) * (span_in**2) / 8
            S = (width_in * depth_in**2) / 6
            stress = M_max / S
            utilization = stress / (material.yield_strength_psi / self.analyzer.safety_factor)

            # Add plastic hinge effect after yielding
            if utilization > 1.0:
                plastic_factor = 1 + (utilization - 1) * 3  # Accelerate after yield
                deflection *= plastic_factor

                # Add "cracking" noise to the beam
                if utilization > 1.2:
                    noise = np.random.normal(0, depth_in * 0.05 * (utilization - 1.2), len(x))
                    deflection += noise

            # Scale for visibility
            visual_scale = 20
            y = depth_in/2 - deflection * visual_scale

            # Color based on utilization
            if utilization < 0.7:
                color = '#22c55e'  # Green
                status = "SAFE"
            elif utilization < 0.9:
                color = '#eab308'  # Yellow
                status = "WARNING"
            elif utilization < 1.0:
                color = '#f97316'  # Orange
                status = "CRITICAL"
            else:
                color = '#ef4444'  # Red
                status = "FAILURE"

            beam_line.set_data(x_ft, y)
            beam_line.set_color(color)
            beam_line.set_linewidth(depth_in * 0.5 * max(0.3, 1 - (utilization - 1) * 0.5) if utilization > 1 else depth_in * 0.5)

            load_text.set_text(f'{current_load:.0f} lb/ft')
            status_text.set_text(f'{status}\nUtilization: {utilization:.0%}\nDeflection: {max(abs(deflection)):.3f}"')
            status_text.set_color(color)

            return beam_line, load_text, status_text

        anim = animation.FuncAnimation(fig, animate, init_func=init, frames=frames,
                                        interval=50, blit=True)

        if save_path:
            if save_path.endswith('.gif'):
                anim.save(save_path, writer='pillow', fps=20)
            else:
                anim.save(save_path, writer='ffmpeg', fps=20)

        return anim

    def visualize_column_buckling(
        self,
        height_ft: float,
        width_in: float,
        depth_in: float,
        material: Material,
        axial_load_lbs: float,
        frames: int = 60,
        save_path: str = None
    ) -> animation.FuncAnimation:
        """
        Animate column buckling failure.
        """
        fig, ax = self._setup_figure(figsize=(8, 12), title="Column Buckling Animation")

        height_in = height_ft * 12
        n_points = 50
        y = np.linspace(0, height_in, n_points)

        # Get critical buckling load
        result = self.analyzer.analyze_column(
            height_ft, width_in, depth_in, material, axial_load_lbs
        )

        critical_load = result.allowable_load_lbs * self.analyzer.safety_factor
        max_load = critical_load * 1.5

        # Initialize
        column_line, = ax.plot([], [], color='#22c55e', linewidth=width_in*2, solid_capstyle='round')
        load_arrow = ax.annotate('', xy=(0, height_in), xytext=(0, height_in + height_in*0.2),
                                  arrowprops=dict(arrowstyle='->', color='#f97316', lw=3))
        load_text = ax.text(width_in*2, height_in*1.1, '', color='#f97316', fontsize=12, fontweight='bold')
        status_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, fontsize=11,
                             verticalalignment='top', fontfamily='monospace', color=self.text_color)

        # Base
        ax.fill_between([-width_in*2, width_in*2], [-height_in*0.05, -height_in*0.05], [0, 0],
                       color='#6366f1', alpha=0.8)

        ax.set_xlim(-height_in*0.3, height_in*0.3)
        ax.set_ylim(-height_in*0.1, height_in*1.3)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, color=self.grid_color)
        ax.set_ylabel('Height (in)')

        def init():
            column_line.set_data([], [])
            return column_line, load_text, status_text

        def animate(frame):
            progress = frame / frames
            current_load = progress * max_load

            utilization = current_load / result.allowable_load_lbs if result.allowable_load_lbs > 0 else 0

            # Buckling shape: sinusoidal lateral displacement
            if utilization > 0.8:
                # Pre-buckling imperfection grows
                amplitude = width_in * 0.1 * ((utilization - 0.8) / 0.2) ** 2
            else:
                amplitude = 0

            if utilization > 1.0:
                # Post-buckling: rapid lateral movement
                amplitude = width_in * (1 + (utilization - 1) * 10)
                # Add instability wobble
                amplitude *= (1 + 0.1 * np.sin(frame * 0.5))

            # First mode buckling shape
            x_displaced = amplitude * np.sin(np.pi * y / height_in)

            # Color
            if utilization < 0.7:
                color = '#22c55e'
                status = "STABLE"
            elif utilization < 0.9:
                color = '#eab308'
                status = "WARNING"
            elif utilization < 1.0:
                color = '#f97316'
                status = "CRITICAL"
            else:
                color = '#ef4444'
                status = "BUCKLING"

            column_line.set_data(x_displaced, y)
            column_line.set_color(color)

            load_text.set_text(f'{current_load/1000:.1f} kips')
            status_text.set_text(f'{status}\nLoad: {current_load/1000:.1f} / {result.allowable_load_lbs/1000:.1f} kips\nSlenderness: {result.slenderness_ratio:.0f}')
            status_text.set_color(color)

            return column_line, load_text, status_text

        anim = animation.FuncAnimation(fig, animate, init_func=init, frames=frames,
                                        interval=50, blit=True)

        if save_path:
            if save_path.endswith('.gif'):
                anim.save(save_path, writer='pillow', fps=20)
            else:
                anim.save(save_path, writer='ffmpeg', fps=20)

        return anim

    def visualize_frame(
        self,
        spans_ft: List[float],
        heights_ft: List[float],
        beam_sizes: List[Tuple[float, float]],  # [(width, depth), ...]
        column_sizes: List[Tuple[float, float]],
        material: Material,
        floor_load_psf: float,
        save_path: str = None
    ) -> Dict:
        """
        Visualize a multi-bay, multi-story frame with stress coloring.

        Args:
            spans_ft: List of bay widths
            heights_ft: List of story heights
            beam_sizes: List of (width, depth) for beams at each level
            column_sizes: List of (width, depth) for columns
            material: Frame material
            floor_load_psf: Floor load
            save_path: Optional save path
        """
        fig, ax = self._setup_figure(figsize=(16, 10), title="Structural Frame Analysis")

        n_bays = len(spans_ft)
        n_stories = len(heights_ft)

        # Calculate column positions
        x_positions = [0]
        for span in spans_ft:
            x_positions.append(x_positions[-1] + span)

        # Calculate level heights
        y_positions = [0]
        for height in heights_ft:
            y_positions.append(y_positions[-1] + height)

        total_width = sum(spans_ft)
        total_height = sum(heights_ft)

        results = {'beams': [], 'columns': []}

        # Draw and analyze columns
        for col_idx in range(n_bays + 1):
            x = x_positions[col_idx]
            tributary = 0
            if col_idx == 0 or col_idx == n_bays:
                tributary = spans_ft[0 if col_idx == 0 else -1] / 2
            else:
                tributary = (spans_ft[col_idx-1] + spans_ft[col_idx]) / 2

            for story in range(n_stories):
                y_bot = y_positions[story]
                y_top = y_positions[story + 1]
                height = heights_ft[story]

                col_w, col_d = column_sizes[min(story, len(column_sizes)-1)]

                # Cumulative load from above
                stories_above = n_stories - story
                axial_load = floor_load_psf * tributary * total_width / n_bays * stories_above

                col_result = self.analyzer.analyze_column(
                    height, col_w, col_d, material, axial_load
                )
                results['columns'].append(col_result)

                # Color by utilization
                util = col_result.utilization_ratio
                color = STRESS_COLORS(min(util / 1.2, 1.0))

                ax.plot([x, x], [y_bot, y_top], color=color, linewidth=col_w*1.5, solid_capstyle='butt')

        # Draw and analyze beams
        for story in range(1, n_stories + 1):
            y = y_positions[story]
            beam_w, beam_d = beam_sizes[min(story-1, len(beam_sizes)-1)]

            for bay in range(n_bays):
                x_start = x_positions[bay]
                x_end = x_positions[bay + 1]
                span = spans_ft[bay]

                # Tributary load
                load_plf = floor_load_psf * (total_width / n_bays) / 2

                beam_result = self.analyzer.analyze_simple_beam(
                    span, beam_w, beam_d, material, load_plf
                )
                results['beams'].append(beam_result)

                # Color by utilization
                util = beam_result.utilization_ratio
                color = STRESS_COLORS(min(util / 1.2, 1.0))

                # Draw with slight deflection
                n_pts = 20
                x_pts = np.linspace(x_start, x_end, n_pts)
                deflection = beam_result.max_deflection_in * np.sin(np.pi * np.linspace(0, 1, n_pts))
                y_pts = y - deflection * 0.5  # Scale for visibility

                ax.plot(x_pts, y_pts, color=color, linewidth=beam_d*0.3, solid_capstyle='butt')

        # Draw supports
        for x in x_positions:
            support = patches.RegularPolygon((x, -total_height*0.03), 3, radius=total_height*0.03,
                                              color='#6366f1', ec='white', linewidth=2)
            ax.add_patch(support)

        # Colorbar
        sm = plt.cm.ScalarMappable(cmap=STRESS_COLORS, norm=plt.Normalize(0, 1.2))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
        cbar.set_label('Utilization Ratio', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)

        # Summary
        beam_fails = sum(1 for r in results['beams'] if not r.passes)
        col_fails = sum(1 for r in results['columns'] if not r.passes)
        max_beam_util = max(r.utilization_ratio for r in results['beams'])
        max_col_util = max(r.utilization_ratio for r in results['columns'])

        status = "✓ ALL PASS" if beam_fails == 0 and col_fails == 0 else f"✗ {beam_fails + col_fails} FAILURES"
        status_color = '#22c55e' if beam_fails == 0 and col_fails == 0 else '#ef4444'

        summary = f"""
{status}
Beams: {len(results['beams']) - beam_fails}/{len(results['beams'])} pass (max util: {max_beam_util:.0%})
Columns: {len(results['columns']) - col_fails}/{len(results['columns'])} pass (max util: {max_col_util:.0%})
"""
        props = dict(boxstyle='round,pad=0.5', facecolor=self.bg_color,
                    edgecolor=status_color, linewidth=2)
        ax.text(0.02, 0.98, summary.strip(), transform=ax.transAxes, fontsize=10,
               verticalalignment='top', fontfamily='monospace', color=self.text_color, bbox=props)

        ax.set_xlim(-total_width*0.1, total_width*1.1)
        ax.set_ylim(-total_height*0.1, total_height*1.1)
        ax.set_xlabel('Width (ft)')
        ax.set_ylabel('Height (ft)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, color=self.grid_color)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=self.bg_color)

        results['figure'] = fig
        return results


# Quick test
if __name__ == "__main__":
    viz = StructuralVisualizer(dark_mode=True)

    print("Testing beam visualization...")
    result = viz.visualize_beam(
        span_ft=16,
        width_in=1.5,
        depth_in=9.25,  # 2x10
        material=Material.wood_spf(),
        uniform_load_plf=80,
        save_path="beam_analysis.png"
    )
    print(f"Beam passes: {result['result'].passes}, Utilization: {result['result'].utilization_ratio:.0%}")

    print("\nTesting frame visualization...")
    frame_result = viz.visualize_frame(
        spans_ft=[20, 20, 20],
        heights_ft=[10, 10],
        beam_sizes=[(3.5, 11.25), (3.5, 9.25)],
        column_sizes=[(5.5, 5.5)],
        material=Material.wood_spf(),
        floor_load_psf=50,
        save_path="frame_analysis.png"
    )

    print("\nVisualizations saved!")
    plt.show()
