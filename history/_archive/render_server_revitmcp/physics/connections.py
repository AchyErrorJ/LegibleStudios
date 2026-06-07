# connections.py
# Structural connections and fastener library
#
# Simpson Strong-Tie style connectors, fasteners, and material estimation

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle, Circle, Polygon, FancyBboxPatch, PathPatch
from matplotlib.path import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class ConnectorType(Enum):
    """Types of structural connectors"""
    JOIST_HANGER = "joist_hanger"
    HURRICANE_TIE = "hurricane_tie"
    HOLD_DOWN = "hold_down"
    STRAP_TIE = "strap_tie"
    POST_BASE = "post_base"
    POST_CAP = "post_cap"
    ANGLE_BRACKET = "angle_bracket"
    RIM_BOARD_HANGER = "rim_board_hanger"
    TRUSS_CLIP = "truss_clip"
    SILL_ANCHOR = "sill_anchor"


class FastenerType(Enum):
    """Types of fasteners"""
    NAIL_16D = "16d_nail"
    NAIL_10D = "10d_nail"
    NAIL_8D = "8d_nail"
    NAIL_6D = "6d_nail"
    SCREW_3IN = "3in_screw"
    SCREW_2_5IN = "2.5in_screw"
    SCREW_1_625IN = "1.625in_screw"
    LAG_BOLT = "lag_bolt"
    CARRIAGE_BOLT = "carriage_bolt"
    ANCHOR_BOLT = "anchor_bolt"
    JOIST_HANGER_NAIL = "joist_hanger_nail"
    ROOFING_NAIL = "roofing_nail"
    SIDING_NAIL = "siding_nail"


@dataclass
class Fastener:
    """Fastener specification"""
    type: FastenerType
    name: str
    length_in: float
    diameter_in: float
    shear_capacity_lbs: float
    withdrawal_capacity_lbs: float
    cost_per_lb: float = 3.50
    pieces_per_lb: int = 50

    @classmethod
    def nail_16d_common(cls):
        return cls(FastenerType.NAIL_16D, "16d Common Nail", 3.5, 0.162, 141, 34, 3.50, 47)

    @classmethod
    def nail_16d_sinker(cls):
        return cls(FastenerType.NAIL_16D, "16d Sinker Nail", 3.25, 0.148, 118, 29, 3.50, 52)

    @classmethod
    def nail_10d_common(cls):
        return cls(FastenerType.NAIL_10D, "10d Common Nail", 3.0, 0.148, 118, 29, 3.50, 66)

    @classmethod
    def nail_8d_common(cls):
        return cls(FastenerType.NAIL_8D, "8d Common Nail", 2.5, 0.131, 94, 23, 3.50, 99)

    @classmethod
    def screw_deck_3in(cls):
        return cls(FastenerType.SCREW_3IN, "3\" Deck Screw", 3.0, 0.138, 150, 180, 8.00, 75)

    @classmethod
    def screw_drywall_1_625(cls):
        return cls(FastenerType.SCREW_1_625IN, "1-5/8\" Drywall Screw", 1.625, 0.125, 80, 100, 6.00, 200)

    @classmethod
    def joist_hanger_nail(cls):
        return cls(FastenerType.JOIST_HANGER_NAIL, "1-1/2\" Joist Hanger Nail", 1.5, 0.148, 118, 0, 5.00, 150)

    @classmethod
    def roofing_nail(cls):
        return cls(FastenerType.ROOFING_NAIL, "1-1/4\" Roofing Nail", 1.25, 0.120, 60, 15, 4.00, 180)

    @classmethod
    def siding_nail_galv(cls):
        return cls(FastenerType.SIDING_NAIL, "2\" Siding Nail (Galv)", 2.0, 0.092, 50, 20, 6.00, 200)


@dataclass
class Connector:
    """Structural connector specification"""
    type: ConnectorType
    model: str
    width_in: float
    height_in: float
    gauge: int
    allowable_load_lbs: float
    fasteners_required: Dict[str, int]  # {"face": count, "joist": count}
    unit_cost: float

    @classmethod
    def lus26(cls):
        """Simpson LUS26 - 2x6 to 2x10 face mount hanger"""
        return cls(ConnectorType.JOIST_HANGER, "LUS26", 1.56, 5.19, 18,
                   1185, {"face": 6, "joist": 4}, 2.45)

    @classmethod
    def lus28(cls):
        """Simpson LUS28 - 2x8 face mount hanger"""
        return cls(ConnectorType.JOIST_HANGER, "LUS28", 1.56, 7.19, 18,
                   1430, {"face": 8, "joist": 6}, 3.15)

    @classmethod
    def lus210(cls):
        """Simpson LUS210 - 2x10 face mount hanger"""
        return cls(ConnectorType.JOIST_HANGER, "LUS210", 1.56, 9.19, 18,
                   1670, {"face": 10, "joist": 8}, 3.85)

    @classmethod
    def lus212(cls):
        """Simpson LUS212 - 2x12 face mount hanger"""
        return cls(ConnectorType.JOIST_HANGER, "LUS212", 1.56, 11.19, 18,
                   1900, {"face": 12, "joist": 10}, 4.55)

    @classmethod
    def h2_5(cls):
        """Simpson H2.5 Hurricane Tie"""
        return cls(ConnectorType.HURRICANE_TIE, "H2.5", 1.31, 4.5, 18,
                   585, {"rafter": 4, "plate": 3}, 0.85)

    @classmethod
    def h10(cls):
        """Simpson H10 Hurricane Tie"""
        return cls(ConnectorType.HURRICANE_TIE, "H10", 3.0, 4.13, 14,
                   1015, {"rafter": 6, "plate": 4}, 1.45)

    @classmethod
    def hdu2(cls):
        """Simpson HDU2 Hold-down"""
        return cls(ConnectorType.HOLD_DOWN, "HDU2", 3.0, 10.31, 14,
                   3075, {"stud": 14, "anchor": 1}, 18.50)

    @classmethod
    def hdu5(cls):
        """Simpson HDU5 Hold-down"""
        return cls(ConnectorType.HOLD_DOWN, "HDU5", 3.0, 14.19, 14,
                   4565, {"stud": 22, "anchor": 1}, 28.75)

    @classmethod
    def a35(cls):
        """Simpson A35 Framing Angle"""
        return cls(ConnectorType.ANGLE_BRACKET, "A35", 1.44, 4.5, 18,
                   510, {"face1": 4, "face2": 4}, 0.95)

    @classmethod
    def lsta12(cls):
        """Simpson LSTA12 Strap Tie 12\""""
        return cls(ConnectorType.STRAP_TIE, "LSTA12", 1.25, 12.0, 20,
                   840, {"each_end": 6}, 1.85)

    @classmethod
    def lsta24(cls):
        """Simpson LSTA24 Strap Tie 24\""""
        return cls(ConnectorType.STRAP_TIE, "LSTA24", 1.25, 24.0, 20,
                   840, {"each_end": 6}, 2.95)

    @classmethod
    def abu44(cls):
        """Simpson ABU44 Post Base"""
        return cls(ConnectorType.POST_BASE, "ABU44", 4.0, 7.0, 12,
                   2950, {"post": 8, "anchor": 2}, 12.50)

    @classmethod
    def bc4(cls):
        """Simpson BC4 Post Cap"""
        return cls(ConnectorType.POST_CAP, "BC4", 3.56, 3.0, 18,
                   1475, {"beam": 4, "post": 4}, 5.25)

    @classmethod
    def mudsill_anchor(cls):
        """1/2\" x 10\" Anchor Bolt"""
        return cls(ConnectorType.SILL_ANCHOR, "1/2\"x10\" AB", 0.5, 10.0, 0,
                   2100, {"nut_washer": 1}, 1.25)


@dataclass
class FastenerSchedule:
    """Fastener requirements for an assembly"""
    framing_nails: Dict[str, int] = field(default_factory=dict)
    sheathing_nails: Dict[str, int] = field(default_factory=dict)
    drywall_screws: int = 0
    siding_fasteners: int = 0
    roofing_fasteners: int = 0
    subfloor_fasteners: int = 0
    connectors: List[Tuple[Connector, int]] = field(default_factory=list)

    def total_fastener_cost(self) -> float:
        """Calculate total fastener material cost"""
        cost = 0.0
        # Framing nails (16d)
        total_framing = sum(self.framing_nails.values())
        cost += (total_framing / 47) * 3.50  # 47 nails per lb

        # Sheathing nails (8d)
        total_sheathing = sum(self.sheathing_nails.values())
        cost += (total_sheathing / 99) * 3.50

        # Drywall screws
        cost += (self.drywall_screws / 200) * 6.00

        # Connectors
        for connector, qty in self.connectors:
            cost += connector.unit_cost * qty

        return cost


class FastenerEstimator:
    """
    Calculate fastener quantities for assemblies.
    Based on standard nailing schedules and code requirements.
    """

    def __init__(self):
        # Standard nailing schedules (per IRC/IBC)
        self.schedules = {
            "stud_to_plate": {"top": 2, "bottom": 2, "type": "16d"},  # End nailed
            "stud_to_plate_toenail": {"nails": 4, "type": "8d"},
            "double_top_plate": {"spacing_in": 16, "type": "16d"},
            "header_to_stud": {"each_end": 4, "type": "16d"},
            "sheathing_edge": {"spacing_in": 6, "type": "8d"},
            "sheathing_field": {"spacing_in": 12, "type": "8d"},
            "sheathing_edge_seismic": {"spacing_in": 4, "type": "8d"},
            "sheathing_edge_high_wind": {"spacing_in": 3, "type": "8d"},
            "subfloor_edge": {"spacing_in": 6, "type": "8d_ring"},
            "subfloor_field": {"spacing_in": 12, "type": "8d_ring"},
            "drywall_edge": {"spacing_in": 8, "type": "screw"},
            "drywall_field": {"spacing_in": 12, "type": "screw"},
            "siding_stud": {"per_stud": 2, "type": "siding"},
            "roofing_shingle": {"per_shingle": 4, "type": "roofing"},
        }

    def estimate_wall_fasteners(
        self,
        wall_length_ft: float,
        wall_height_ft: float,
        stud_spacing_in: float = 16,
        has_sheathing: bool = True,
        has_drywall: bool = True,
        has_siding: bool = True,
        seismic_zone: bool = False,
        high_wind: bool = False,
    ) -> FastenerSchedule:
        """
        Estimate fasteners for a wall section.

        Args:
            wall_length_ft: Wall length
            wall_height_ft: Wall height
            stud_spacing_in: Stud spacing (16 or 24)
            has_sheathing: Wall has OSB/plywood sheathing
            has_drywall: Wall has interior drywall
            has_siding: Wall has exterior siding
            seismic_zone: High seismic design category
            high_wind: High wind zone (>110 mph)

        Returns:
            FastenerSchedule with quantities
        """
        schedule = FastenerSchedule()
        wall_length_in = wall_length_ft * 12
        wall_height_in = wall_height_ft * 12

        # Number of studs
        num_studs = int(wall_length_in / stud_spacing_in) + 1

        # Framing nails
        # Bottom plate to stud (2 per stud, end nailed or 4 toenailed)
        schedule.framing_nails["bottom_plate"] = num_studs * 2

        # Top plate to stud
        schedule.framing_nails["top_plate"] = num_studs * 2

        # Double top plate splice
        top_plate_nails = int(wall_length_in / 16) * 2  # Every 16"
        schedule.framing_nails["double_plate"] = top_plate_nails

        # Sheathing nails
        if has_sheathing:
            # Edge nailing
            if seismic_zone:
                edge_spacing = 4
            elif high_wind:
                edge_spacing = 3
            else:
                edge_spacing = 6

            # Perimeter of wall
            perimeter_in = 2 * (wall_length_in + wall_height_in)
            edge_nails = int(perimeter_in / edge_spacing)

            # Field nailing (12" OC along studs)
            field_nails_per_stud = int(wall_height_in / 12)
            field_nails = field_nails_per_stud * num_studs

            schedule.sheathing_nails["edge"] = edge_nails
            schedule.sheathing_nails["field"] = field_nails

        # Drywall screws
        if has_drywall:
            # Edge: 8" OC, Field: 12" OC
            sheets_high = int(np.ceil(wall_height_in / 48))
            sheets_wide = int(np.ceil(wall_length_in / 96))
            total_sheets = sheets_high * sheets_wide

            # Perimeter screws per sheet
            sheet_perimeter = 2 * (48 + 96)
            edge_screws = int(sheet_perimeter / 8)

            # Field screws (3 studs per 8' sheet @ 12" OC)
            field_screws = 3 * int(48 / 12)

            schedule.drywall_screws = total_sheets * (edge_screws + field_screws)

        # Siding fasteners
        if has_siding:
            # 2 nails per stud, every course (~8" exposure)
            courses = int(wall_height_in / 8)
            schedule.siding_fasteners = courses * num_studs * 2

        return schedule

    def estimate_floor_fasteners(
        self,
        floor_length_ft: float,
        floor_width_ft: float,
        joist_spacing_in: float = 16,
        has_subfloor: bool = True,
        subfloor_glued: bool = True,
    ) -> FastenerSchedule:
        """
        Estimate fasteners for a floor section.
        """
        schedule = FastenerSchedule()
        floor_length_in = floor_length_ft * 12
        floor_width_in = floor_width_ft * 12

        # Number of joists
        num_joists = int(floor_width_in / joist_spacing_in) + 1

        # Joist to rim/band nailing (3 per end)
        schedule.framing_nails["joist_to_rim"] = num_joists * 3 * 2

        # Joist hangers
        hanger = Connector.lus210()  # Assume 2x10
        schedule.connectors.append((hanger, num_joists * 2))

        # Subfloor fastening
        if has_subfloor:
            # 4x8 sheets
            sheets = int(np.ceil(floor_length_in / 96)) * int(np.ceil(floor_width_in / 48))

            # Edge nailing (6" OC)
            sheet_perimeter = 2 * (48 + 96)
            edge_per_sheet = int(sheet_perimeter / 6)

            # Field nailing (12" OC along joists)
            joists_per_sheet = int(48 / joist_spacing_in) + 1
            field_per_sheet = joists_per_sheet * int(96 / 12)

            schedule.subfloor_fasteners = sheets * (edge_per_sheet + field_per_sheet)

            if subfloor_glued:
                # Note: glue reduces fastener requirement by ~30% but we keep full count
                pass

        return schedule

    def estimate_roof_fasteners(
        self,
        roof_length_ft: float,
        roof_width_ft: float,
        rafter_spacing_in: float = 24,
        has_sheathing: bool = True,
        has_shingles: bool = True,
        hurricane_ties: bool = False,
    ) -> FastenerSchedule:
        """
        Estimate fasteners for a roof section.
        """
        schedule = FastenerSchedule()
        roof_length_in = roof_length_ft * 12
        roof_width_in = roof_width_ft * 12

        # Number of rafters/trusses
        num_rafters = int(roof_length_in / rafter_spacing_in) + 1

        # Rafter to plate (toenailed: 3 per side)
        schedule.framing_nails["rafter_to_plate"] = num_rafters * 6

        # Ridge connection (4 per rafter)
        schedule.framing_nails["ridge"] = num_rafters * 4

        # Hurricane ties
        if hurricane_ties:
            tie = Connector.h2_5()
            schedule.connectors.append((tie, num_rafters * 2))  # Both ends

        # Sheathing
        if has_sheathing:
            sheets = int(np.ceil(roof_length_in / 96)) * int(np.ceil(roof_width_in / 48))
            sheet_perimeter = 2 * (48 + 96)
            edge_per_sheet = int(sheet_perimeter / 6)
            rafters_per_sheet = int(48 / rafter_spacing_in) + 1
            field_per_sheet = rafters_per_sheet * int(96 / 12)
            schedule.sheathing_nails["edge"] = sheets * edge_per_sheet
            schedule.sheathing_nails["field"] = sheets * field_per_sheet

        # Roofing nails
        if has_shingles:
            # Approx 320 nails per square (100 sq ft)
            squares = (roof_length_ft * roof_width_ft) / 100
            schedule.roofing_fasteners = int(squares * 320)

        return schedule


class ConnectionRenderer:
    """
    Render structural connections in section details.
    """

    def __init__(self, dark_mode: bool = True):
        self.dark_mode = dark_mode
        self.connector_color = '#71717a' if dark_mode else '#52525b'
        self.fastener_color = '#a1a1aa' if dark_mode else '#71717a'
        self.label_color = '#e4e4e7' if dark_mode else '#27272a'

    def draw_joist_hanger(
        self,
        ax,
        x: float,
        y: float,
        connector: Connector,
        scale: float = 1.0,
        show_fasteners: bool = True,
        show_label: bool = True
    ):
        """Draw a joist hanger connector"""
        w = connector.width_in * scale
        h = connector.height_in * scale

        # Main body (U-shape)
        # Left flange
        left_flange = Rectangle((x - w/2 - 0.1*scale, y), 0.1*scale, h,
                                  facecolor=self.connector_color, edgecolor='#27272a',
                                  linewidth=0.5)
        ax.add_patch(left_flange)

        # Right flange
        right_flange = Rectangle((x + w/2, y), 0.1*scale, h,
                                   facecolor=self.connector_color, edgecolor='#27272a',
                                   linewidth=0.5)
        ax.add_patch(right_flange)

        # Bottom seat
        bottom = Rectangle((x - w/2 - 0.1*scale, y), w + 0.2*scale, 0.1*scale,
                           facecolor=self.connector_color, edgecolor='#27272a',
                           linewidth=0.5)
        ax.add_patch(bottom)

        # Top flanges (mounting tabs)
        top_left = Rectangle((x - w/2 - 0.3*scale, y + h - 0.5*scale), 0.3*scale, 0.5*scale,
                              facecolor=self.connector_color, edgecolor='#27272a',
                              linewidth=0.5)
        top_right = Rectangle((x + w/2, y + h - 0.5*scale), 0.3*scale, 0.5*scale,
                               facecolor=self.connector_color, edgecolor='#27272a',
                               linewidth=0.5)
        ax.add_patch(top_left)
        ax.add_patch(top_right)

        # Fastener holes
        if show_fasteners:
            # Face nails (on flanges)
            face_count = connector.fasteners_required.get("face", 6)
            spacing = (h - 0.5*scale) / (face_count // 2 + 1)
            for i in range(face_count // 2):
                y_pos = y + 0.3*scale + i * spacing
                # Left side
                ax.add_patch(Circle((x - w/2 - 0.15*scale, y_pos), 0.04*scale,
                                    facecolor=self.fastener_color, edgecolor='#27272a'))
                # Right side
                ax.add_patch(Circle((x + w/2 + 0.05*scale, y_pos), 0.04*scale,
                                    facecolor=self.fastener_color, edgecolor='#27272a'))

        # Label
        if show_label:
            ax.text(x, y - 0.3*scale, connector.model,
                   ha='center', va='top', fontsize=7, color=self.label_color,
                   fontfamily='monospace')

    def draw_hurricane_tie(
        self,
        ax,
        x: float,
        y: float,
        connector: Connector,
        scale: float = 1.0,
        orientation: str = "right",  # "left" or "right"
        show_label: bool = True
    ):
        """Draw a hurricane tie/clip"""
        w = connector.width_in * scale
        h = connector.height_in * scale

        flip = -1 if orientation == "left" else 1

        # Main strap body (bent shape)
        # Vertical part on plate
        vert = Rectangle((x - 0.05*scale, y), 0.1*scale, h * 0.4,
                         facecolor=self.connector_color, edgecolor='#27272a',
                         linewidth=0.5)
        ax.add_patch(vert)

        # Bent part going up rafter
        bent_pts = [
            (x - 0.05*scale, y + h * 0.4),
            (x + flip * w * 0.3, y + h * 0.5),
            (x + flip * w * 0.4, y + h),
            (x + flip * w * 0.4 + 0.1*scale, y + h),
            (x + flip * w * 0.3 + 0.1*scale, y + h * 0.5),
            (x + 0.05*scale, y + h * 0.4),
        ]
        bent = Polygon(bent_pts, facecolor=self.connector_color, edgecolor='#27272a',
                       linewidth=0.5, closed=True)
        ax.add_patch(bent)

        # Nail holes
        for i in range(3):
            y_pos = y + 0.1*scale + i * 0.12*scale
            ax.add_patch(Circle((x, y_pos), 0.03*scale,
                                facecolor=self.fastener_color, edgecolor='#27272a'))

        if show_label:
            ax.text(x + flip * 0.5*scale, y + h * 0.7, connector.model,
                   ha='center', va='center', fontsize=6, color=self.label_color,
                   fontfamily='monospace', rotation=45 * flip)

    def draw_hold_down(
        self,
        ax,
        x: float,
        y: float,
        connector: Connector,
        scale: float = 1.0,
        show_label: bool = True
    ):
        """Draw a hold-down connector"""
        w = connector.width_in * scale
        h = connector.height_in * scale

        # Main body (vertical strap with holes)
        body = Rectangle((x - w/2, y), w, h,
                         facecolor=self.connector_color, edgecolor='#27272a',
                         linewidth=1)
        ax.add_patch(body)

        # Bolt holes pattern
        num_holes = connector.fasteners_required.get("stud", 10)
        rows = num_holes // 2
        spacing = (h - 1*scale) / (rows + 1)

        for i in range(rows):
            y_pos = y + 0.5*scale + (i + 1) * spacing
            ax.add_patch(Circle((x - w/4, y_pos), 0.05*scale,
                                facecolor=self.fastener_color, edgecolor='#27272a'))
            ax.add_patch(Circle((x + w/4, y_pos), 0.05*scale,
                                facecolor=self.fastener_color, edgecolor='#27272a'))

        # Base plate with anchor hole
        base = Rectangle((x - w/2 - 0.2*scale, y - 0.2*scale), w + 0.4*scale, 0.2*scale,
                         facecolor=self.connector_color, edgecolor='#27272a',
                         linewidth=1)
        ax.add_patch(base)

        # Anchor bolt hole
        ax.add_patch(Circle((x, y - 0.1*scale), 0.08*scale,
                           facecolor='#1f2937', edgecolor='#27272a', linewidth=1))

        if show_label:
            ax.text(x + w/2 + 0.2*scale, y + h/2, connector.model,
                   ha='left', va='center', fontsize=7, color=self.label_color,
                   fontfamily='monospace')

    def draw_strap_tie(
        self,
        ax,
        x: float,
        y: float,
        connector: Connector,
        scale: float = 1.0,
        angle: float = 0,  # degrees
        show_label: bool = True
    ):
        """Draw a strap tie"""
        w = connector.width_in * scale
        h = connector.height_in * scale

        # Simple rectangular strap
        strap = Rectangle((x, y - w/2), h, w,
                          facecolor=self.connector_color, edgecolor='#27272a',
                          linewidth=0.5, angle=angle)
        ax.add_patch(strap)

        # Nail holes (simplified)
        num_each_end = connector.fasteners_required.get("each_end", 6)
        hole_spacing = 0.15 * scale
        for i in range(num_each_end // 2):
            # Left end
            ax.add_patch(Circle((x + 0.3*scale + i * hole_spacing, y), 0.03*scale,
                                facecolor=self.fastener_color, edgecolor='#27272a'))
            # Right end
            ax.add_patch(Circle((x + h - 0.3*scale - i * hole_spacing, y), 0.03*scale,
                                facecolor=self.fastener_color, edgecolor='#27272a'))

        if show_label:
            ax.text(x + h/2, y - w/2 - 0.2*scale, connector.model,
                   ha='center', va='top', fontsize=6, color=self.label_color,
                   fontfamily='monospace')

    def draw_anchor_bolt(
        self,
        ax,
        x: float,
        y: float,
        embed_depth: float = 7.0,
        scale: float = 1.0,
        show_label: bool = True
    ):
        """Draw a foundation anchor bolt"""
        bolt_dia = 0.5 * scale
        embed = embed_depth * scale

        # Bolt shaft (in concrete)
        ax.plot([x, x], [y, y - embed], color='#71717a', linewidth=2)

        # J-hook at bottom
        hook_pts = [(x, y - embed), (x - 0.2*scale, y - embed - 0.3*scale),
                    (x - 0.3*scale, y - embed - 0.2*scale)]
        ax.plot([p[0] for p in hook_pts], [p[1] for p in hook_pts],
               color='#71717a', linewidth=2)

        # Nut and washer above sill
        washer = Rectangle((x - 0.4*scale, y + 0.1*scale), 0.8*scale, 0.1*scale,
                           facecolor='#a1a1aa', edgecolor='#27272a', linewidth=0.5)
        nut = Rectangle((x - 0.25*scale, y + 0.2*scale), 0.5*scale, 0.3*scale,
                        facecolor='#71717a', edgecolor='#27272a', linewidth=0.5)
        ax.add_patch(washer)
        ax.add_patch(nut)

        if show_label:
            ax.text(x + 0.5*scale, y, '1/2"×10" AB',
                   ha='left', va='center', fontsize=6, color=self.label_color,
                   fontfamily='monospace')

    def draw_nail_pattern(
        self,
        ax,
        x: float,
        y: float,
        width: float,
        height: float,
        spacing_edge: float = 6,
        spacing_field: float = 12,
        scale: float = 1.0,
        pattern_type: str = "sheathing"  # "sheathing", "drywall", "subfloor"
    ):
        """Draw nailing pattern for sheathing/drywall"""
        nail_size = 0.03 * scale

        # Edge nails (perimeter)
        # Top edge
        for xi in np.arange(x, x + width, spacing_edge / 12 * scale):
            ax.add_patch(Circle((xi, y + height), nail_size,
                                facecolor=self.fastener_color, edgecolor='none'))
        # Bottom edge
        for xi in np.arange(x, x + width, spacing_edge / 12 * scale):
            ax.add_patch(Circle((xi, y), nail_size,
                                facecolor=self.fastener_color, edgecolor='none'))
        # Left edge
        for yi in np.arange(y, y + height, spacing_edge / 12 * scale):
            ax.add_patch(Circle((x, yi), nail_size,
                                facecolor=self.fastener_color, edgecolor='none'))
        # Right edge
        for yi in np.arange(y, y + height, spacing_edge / 12 * scale):
            ax.add_patch(Circle((x + width, yi), nail_size,
                                facecolor=self.fastener_color, edgecolor='none'))


# Quick test
if __name__ == "__main__":
    estimator = FastenerEstimator()

    print("=== Wall Fastener Estimate (8' x 10' wall) ===")
    wall_schedule = estimator.estimate_wall_fasteners(
        wall_length_ft=10,
        wall_height_ft=8,
        stud_spacing_in=16,
        has_sheathing=True,
        has_drywall=True,
        has_siding=True
    )
    print(f"Framing nails: {wall_schedule.framing_nails}")
    print(f"Sheathing nails: {wall_schedule.sheathing_nails}")
    print(f"Drywall screws: {wall_schedule.drywall_screws}")
    print(f"Siding nails: {wall_schedule.siding_fasteners}")

    print("\n=== Floor Fastener Estimate (12' x 20' floor) ===")
    floor_schedule = estimator.estimate_floor_fasteners(
        floor_length_ft=20,
        floor_width_ft=12,
        joist_spacing_in=16
    )
    print(f"Framing nails: {floor_schedule.framing_nails}")
    print(f"Subfloor fasteners: {floor_schedule.subfloor_fasteners}")
    print(f"Joist hangers: {floor_schedule.connectors}")

    print("\n=== Connector Library ===")
    connectors = [
        Connector.lus26(), Connector.lus210(),
        Connector.h2_5(), Connector.hdu2(),
        Connector.a35(), Connector.lsta24()
    ]
    for c in connectors:
        print(f"{c.model}: {c.type.value}, {c.allowable_load_lbs} lbs, ${c.unit_cost:.2f}")
