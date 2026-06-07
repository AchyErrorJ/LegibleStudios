"""
Normalized Constraint Solver - Produces simple building shapes (rect/L) with constraint satisfaction.
"""
import math
import time
from typing import List, Dict, Tuple
from solver_suite import BaseSolver, PlacedLayout, PlacedRoom, Rect, Point, SolverType
from room_relationships import RoomNode


class NormalizedConstraintSolver(BaseSolver):
    """
    Constraint solver that produces normalized building shapes (rectangular or L-shaped).

    Algorithm:
    1. Determine optimal building shape (rectangle or L) based on room count and zones
    2. Divide shape into zones (public, private, service, circulation)
    3. Place rooms within their zone using constraint satisfaction
    4. Ensure adjacencies are satisfied through zone proximity
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.NORMALIZED_CONSTRAINT

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Solve using normalized shape approach."""
        start_time = time.time()
        self._start_timer()
        layout = PlacedLayout()

        rooms = list(self.graph.rooms.values())
        if not rooms:
            return layout

        # Step 1: Determine best building shape
        shape_type = self._determine_building_shape(rooms)

        # Step 2: Group rooms by zone
        zones = self._group_rooms_by_zone(rooms)

        # Step 3: Allocate space for each zone within the shape
        zone_allocations = self._allocate_zones(shape_type, zones)

        # Step 4: Place rooms within each zone
        # Merge transition/circulation into public zone for placement
        merged_zones = dict(zones)
        if 'public' in zone_allocations:
            # Add transition and circulation rooms to public zone
            if zones.get('transition'):
                merged_zones['public'] = merged_zones.get('public', []) + zones['transition']
            if zones.get('circulation'):
                merged_zones['public'] = merged_zones.get('public', []) + zones['circulation']

        unplaced_rooms = []
        for zone_name, zone_rooms in merged_zones.items():
            if zone_name not in zone_allocations or not zone_rooms:
                continue

            allocation = zone_allocations[zone_name]
            placed_in_zone = self._place_rooms_in_zone(
                layout, zone_rooms, allocation,
                zone_allocations, zones
            )

            # Track rooms that weren't placed
            for room in zone_rooms:
                if room.id not in layout.rooms:
                    unplaced_rooms.append(room)

        # Step 4b: Place any unplaced rooms in remaining space
        if unplaced_rooms:
            self._place_unplaced_rooms(layout, unplaced_rooms, zone_allocations)

        # Step 5: Resolve any remaining overlaps
        self._resolve_overlaps(layout)

        # Step 6: Optimize adjacencies
        self._optimize_adjacencies(layout)

        layout.iterations = self.iterations
        layout.solve_time_ms = (time.time() - start_time) * 1000
        layout.score = self.score_layout(layout)
        layout.is_complete = len(layout.rooms) == len(rooms)

        return layout

    def _determine_building_shape(self, rooms: List[RoomNode]) -> str:
        """Determine optimal building shape based on room configuration."""
        total_area = sum(r.target_area for r in rooms)
        room_count = len(rooms)

        # Calculate aspect ratio preference
        width_ratio = self.width / self.depth

        # Simple heuristic: use L-shape for larger houses with clear zone separation
        zones = self._group_rooms_by_zone(rooms)
        has_clear_zones = len([z for z in zones.values() if z]) >= 3

        if room_count > 10 and has_clear_zones and width_ratio > 1.2:
            return 'L'
        return 'rectangle'

    def _group_rooms_by_zone(self, rooms: List[RoomNode]) -> Dict[str, List[RoomNode]]:
        """Group rooms by their zone type."""
        zones = {
            'public': [],
            'private': [],
            'service': [],
            'circulation': [],
            'transition': []
        }

        for room in rooms:
            zone_name = str(room.zone).lower()
            if 'public' in zone_name:
                zones['public'].append(room)
            elif 'private' in zone_name:
                zones['private'].append(room)
            elif 'service' in zone_name:
                zones['service'].append(room)
            elif 'circulation' in zone_name:
                zones['circulation'].append(room)
            elif 'transition' in zone_name:
                zones['transition'].append(room)
            else:
                zones['public'].append(room)  # Default

        return zones

    def _allocate_zones(self, shape_type: str, zones: Dict[str, List[RoomNode]]) -> Dict[str, Dict]:
        """Allocate space for each zone within the building shape."""
        allocations = {}

        # Calculate area for each zone
        zone_areas = {}
        for zone_name, rooms in zones.items():
            area = sum(r.target_area for r in rooms)
            zone_areas[zone_name] = area

        if shape_type == 'rectangle':
            allocations = self._allocate_rectangle(zones, zone_areas)
        else:  # L-shape
            allocations = self._allocate_l_shape(zones, zone_areas)

        return allocations

    def _allocate_rectangle(self, zones: Dict[str, List[RoomNode]], zone_areas: Dict[str, float]) -> Dict[str, Dict]:
        """Allocate zones in rectangular configuration with all zones merged into public/private/service."""
        allocations = {}

        # Calculate total area needed for each zone type
        total_public = zone_areas.get('public', 0) + zone_areas.get('transition', 0) + zone_areas.get('circulation', 0)
        total_private = zone_areas.get('private', 0)
        total_service = zone_areas.get('service', 0)

        total_area = total_public + total_private + total_service

        # Scale factors to fit within building (with buffer for circulation)
        buffer_factor = 1.15  # Add 15% for walls/corridors
        scale = min(1.0, (self.width * self.depth) / (total_area * buffer_factor)) if total_area > 0 else 1.0

        # Allocate space proportionally
        available_width = self.width
        available_depth = self.depth

        # Service zone on right side (typically 20-35% of width)
        if total_service > 0:
            service_ratio = (total_service * buffer_factor * scale) / (self.width * self.depth)
            service_width = min(max(service_ratio * self.width, 2.5), self.width * 0.35)
        else:
            service_width = 0

        # Public zone at front (bottom), includes transition and circulation
        if total_public > 0:
            public_ratio = (total_public * buffer_factor * scale) / ((self.width - service_width) * self.depth)
            public_height = min(max(public_ratio * self.depth, 2.5), self.depth * 0.5)
        else:
            public_height = 0

        # Private zone takes remaining space
        private_height = max(0.1, self.depth - public_height)

        # Create allocations
        if total_public > 0:
            allocations['public'] = {
                'x': 0, 'y': 0,
                'width': self.width - service_width,
                'height': public_height
            }

        if total_private > 0:
            allocations['private'] = {
                'x': 0,
                'y': public_height,
                'width': self.width - service_width,
                'height': private_height
            }

        if total_service > 0:
            allocations['service'] = {
                'x': self.width - service_width,
                'y': 0,
                'width': service_width,
                'height': self.depth
            }

        # Also allocate transition and circulation within public zone
        # These are subsets of public zone
        if zones.get('transition'):
            trans_height = min(3.0, public_height * 0.6)
            allocations['transition'] = {
                'x': 0, 'y': 0,
                'width': min(3.0, (self.width - service_width) * 0.25),
                'height': trans_height
            }

        if zones.get('circulation'):
            # Hallway runs between public and private
            allocations['circulation'] = {
                'x': min(2.0, (self.width - service_width) * 0.15),
                'y': max(0, public_height - 2.0),
                'width': max(0.1, (self.width - service_width) - 4.0),
                'height': min(2.0, private_height * 0.2)
            }

        return allocations

    def _allocate_l_shape(self, zones: Dict[str, List[RoomNode]], zone_areas: Dict[str, float]) -> Dict[str, Dict]:
        """Allocate zones in L-shaped configuration."""
        allocations = {}

        main_width = self.width * 0.65
        wing_width = self.width * 0.35

        # Public zone in main wing (front)
        if zones.get('public'):
            public_area = zone_areas.get('public', 0)
            public_height = (public_area / main_width) * 1.3 if main_width > 0 else 3
            allocations['public'] = {
                'x': 0, 'y': 0,
                'width': main_width,
                'height': min(public_height, self.depth * 0.35)
            }

        # Private zone in main wing (back)
        if zones.get('private'):
            pub_height = allocations.get('public', {}).get('height', 0)
            allocations['private'] = {
                'x': 0, 'y': pub_height,
                'width': main_width,
                'height': max(0.1, self.depth - pub_height)
            }

        # Service zone in side wing
        if zones.get('service'):
            allocations['service'] = {
                'x': main_width, 'y': 0,
                'width': wing_width,
                'height': self.depth * 0.6
            }

        return allocations

    def _place_rooms_in_zone(
        self, layout: PlacedLayout, rooms: List[RoomNode],
        allocation: Dict, all_allocations: Dict, all_zones: Dict
    ) -> bool:
        """Place rooms within a zone allocation using shelf algorithm with overlap checking."""
        zone_x = allocation['x']
        zone_y = allocation['y']
        zone_w = allocation['width']
        zone_h = allocation['height']

        if zone_w <= 0 or zone_h <= 0:
            return False

        # Sort rooms by size (largest first)
        sorted_rooms = sorted(rooms, key=lambda r: -r.target_area)

        for room in sorted_rooms:
            if room.id in layout.rooms:
                continue  # Already placed

            area = room.target_area
            width = max(room.min_width, math.sqrt(area))
            depth = area / width if width > 0 else room.min_depth

            width = self.snap_to_grid(width)
            depth = self.snap_to_grid(depth)
            width = max(width, room.min_width)
            depth = max(depth, room.min_depth)

            # Try to find a valid position using shelf algorithm
            placed = self._try_shelf_placement(layout, room, zone_x, zone_y, zone_w, zone_h, width, depth)

            if not placed:
                # Try with reduced size
                for scale in [0.8, 0.7, 0.6]:
                    reduced_width = self.snap_to_grid(width * scale)
                    reduced_depth = self.snap_to_grid(depth * scale)
                    reduced_width = max(reduced_width, room.min_width * 0.8)
                    reduced_depth = max(reduced_depth, room.min_depth * 0.8)

                    placed = self._try_shelf_placement(layout, room, zone_x, zone_y, zone_w, zone_h,
                                                      reduced_width, reduced_depth)
                    if placed:
                        break

        return True

    def _try_shelf_placement(self, layout: PlacedLayout, room: RoomNode,
                             zone_x: float, zone_y: float, zone_w: float, zone_h: float,
                             width: float, depth: float) -> bool:
        """Try to place a room using shelf algorithm with overlap checking."""
        step = 0.5  # Grid step for shelf placement

        # Try shelf positions
        y = zone_y
        while y + depth <= zone_y + zone_h:
            x = zone_x
            row_height = 0

            while x + width <= zone_x + zone_w:
                rect = Rect(x, y, width, depth)

                # Check if position is valid (no overlaps, in bounds)
                if self._is_valid_placement(layout, rect, room.id):
                    # Check if within zone
                    if (rect.x >= zone_x and rect.y >= zone_y and
                        rect.x + rect.width <= zone_x + zone_w and
                        rect.y + rect.height <= zone_y + zone_h):

                        placed = PlacedRoom(room, rect)
                        layout.add_room(placed)
                        return True

                x += step
                row_height = max(row_height, depth)

            y += step

        return False

    def _place_rooms_in_zone_relaxed(
        self, layout: PlacedLayout, rooms: List[RoomNode], allocation: Dict
    ) -> bool:
        """Place rooms with relaxed constraints (smaller sizes)."""
        zone_x = allocation['x']
        zone_y = allocation['y']
        zone_w = allocation['width']
        zone_h = allocation['height']

        if zone_w <= 0 or zone_h <= 0:
            return False

        # Calculate scale factor to fit all rooms
        total_min_area = sum(r.min_area for r in rooms)
        zone_area = zone_w * zone_h
        scale = min(1.0, (zone_area / total_min_area) ** 0.5) if total_min_area > 0 else 1.0

        current_x = zone_x
        current_y = zone_y
        row_height = 0

        for room in rooms:
            if room.id in layout.rooms:
                continue  # Already placed

            area = room.min_area * scale * scale
            width = max(room.min_width * scale, math.sqrt(area))
            depth = area / width if width > 0 else room.min_depth * scale

            width = self.snap_to_grid(width)
            depth = self.snap_to_grid(depth)

            if current_x + width > zone_x + zone_w:
                current_x = zone_x
                current_y += row_height
                row_height = 0

            if current_y + depth > zone_y + zone_h:
                current_y = max(zone_y, zone_y + zone_h - depth)

            rect = Rect(current_x, current_y, width, depth)
            placed = PlacedRoom(room, rect)
            layout.add_room(placed)

            current_x += width
            row_height = max(row_height, depth)

        return True

    def _resolve_overlaps(self, layout: PlacedLayout):
        """Resolve any overlapping rooms."""
        for iteration in range(50):
            overlaps_found = False
            rooms = list(layout.rooms.values())

            for i, r1 in enumerate(rooms):
                for r2 in rooms[i+1:]:
                    if r1.rect.intersects(r2.rect):
                        overlaps_found = True

                        # Calculate separation
                        dx = r1.rect.center.x - r2.rect.center.x
                        dy = r1.rect.center.y - r2.rect.center.y
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001

                        sep = 0.3
                        sep_x = (dx / dist) * sep
                        sep_y = (dy / dist) * sep

                        r1.rect.x = max(0, min(r1.rect.x + sep_x, self.width - r1.rect.width))
                        r1.rect.y = max(0, min(r1.rect.y + sep_y, self.depth - r1.rect.height))
                        r2.rect.x = max(0, min(r2.rect.x - sep_x, self.width - r2.rect.width))
                        r2.rect.y = max(0, min(r2.rect.y - sep_y, self.depth - r2.rect.height))

            if not overlaps_found:
                break

    def _optimize_adjacencies(self, layout: PlacedLayout):
        """Optimize room positions to improve adjacency satisfaction without causing overlaps."""
        for iteration in range(30):
            improved = False

            for room_id, placed in layout.rooms.items():
                neighbors = self.graph.get_neighbors(room_id)
                if not neighbors:
                    continue

                # Calculate target position based on neighbors
                tx, ty = 0.0, 0.0
                count = 0

                for neighbor_id in neighbors:
                    neighbor = layout.rooms.get(neighbor_id)
                    if neighbor:
                        tx += neighbor.rect.center.x
                        ty += neighbor.rect.center.y
                        count += 1

                if count > 0:
                    tx /= count
                    ty /= count

                    cx, cy = placed.rect.center.x, placed.rect.center.y
                    dx = (tx - cx) * 0.1
                    dy = (ty - cy) * 0.1

                    new_x = max(0, min(placed.rect.x + dx, self.width - placed.rect.width))
                    new_y = max(0, min(placed.rect.y + dy, self.depth - placed.rect.height))

                    if abs(dx) > 0.01 or abs(dy) > 0.01:
                        # Save old position
                        old_x, old_y = placed.rect.x, placed.rect.y

                        # Try new position
                        placed.rect.x = new_x
                        placed.rect.y = new_y

                        # Check if new position causes overlap
                        has_overlap = False
                        for other_id, other in layout.rooms.items():
                            if other_id == room_id:
                                continue
                            if placed.rect.intersects(other.rect):
                                has_overlap = True
                                break

                        if has_overlap:
                            # Revert to old position
                            placed.rect.x = old_x
                            placed.rect.y = old_y
                        else:
                            improved = True

            if not improved:
                break

    def _place_unplaced_rooms(self, layout: PlacedLayout, rooms: List[RoomNode], zone_allocations: Dict):
        """Place any remaining rooms in available gaps."""
        if not rooms:
            return

        # Find available spaces (gaps between placed rooms and zone boundaries)
        for room in rooms:
            if room.id in layout.rooms:
                continue

            # Try to find a spot in any zone with available space
            placed = False

            for zone_name, alloc in zone_allocations.items():
                if self._try_place_room_in_gap(layout, room, alloc):
                    placed = True
                    break

            if not placed:
                # Last resort: scan entire building at smaller step size
                # Try progressively smaller sizes
                for scale in [1.0, 0.8, 0.6]:
                    target_area = max(room.min_area, room.target_area * scale * scale)
                    width = max(room.min_width * scale, math.sqrt(target_area))
                    depth = target_area / width if width > 0 else room.min_depth * scale
                    width = self.snap_to_grid(width)
                    depth = self.snap_to_grid(depth)

                    # Scan entire building footprint
                    found_spot = False
                    for x in [i * 0.25 for i in range(int(self.width / 0.25) + 1)]:
                        for y in [i * 0.25 for i in range(int(self.depth / 0.25) + 1)]:
                            if x + width > self.width or y + depth > self.depth:
                                continue
                            rect = Rect(x, y, width, depth)
                            if self._is_valid_placement(layout, rect, room.id):
                                placed_room = PlacedRoom(room, rect)
                                layout.add_room(placed_room)
                                placed = True
                                found_spot = True
                                break
                        if found_spot:
                            break
                    if found_spot:
                        break

    def _try_place_room_in_gap(self, layout: PlacedLayout, room: RoomNode, allocation: Dict) -> bool:
        """Try to place a room in a gap within the allocation."""
        zone_x = allocation['x']
        zone_y = allocation['y']
        zone_w = allocation['width']
        zone_h = allocation['height']

        width = max(room.min_width, 2.0)
        depth = max(room.min_depth, room.target_area / width if width > 0 else 2.0)
        width = self.snap_to_grid(width)
        depth = self.snap_to_grid(depth)

        # Simple grid scan for available spot
        step = 0.5
        for x in [zone_x + i * step for i in range(int(zone_w / step))]:
            for y in [zone_y + i * step for i in range(int(zone_h / step))]:
                if x + width > zone_x + zone_w or y + depth > zone_y + zone_h:
                    continue

                rect = Rect(x, y, width, depth)
                if self._is_valid_placement(layout, rect, room.id):
                    placed = PlacedRoom(room, rect)
                    layout.add_room(placed)
                    return True

        return False

    def _is_valid_placement(self, layout: PlacedLayout, rect: Rect, exclude_room_id: str = None) -> bool:
        """Check if a rectangle is valid (in bounds and no overlaps)."""
        # Check bounds
        if rect.x < 0 or rect.y < 0:
            return False
        if rect.x + rect.width > self.width or rect.y + rect.height > self.depth:
            return False

        # Check overlaps with placed rooms
        for room_id, placed in layout.rooms.items():
            if room_id == exclude_room_id:
                continue
            if rect.intersects(placed.rect):
                return False

        return True
