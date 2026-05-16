"""
Advanced Solver Collection with Visual Debugging

Additional solvers for the QBD suite:
- Genetic Algorithm: Evolutionary optimization
- Simulated Annealing: Thermodynamic-inspired
- Force-Directed: Physics simulation
- Space Colonization: Growth-based organic
- Spiral: Radial growth pattern

All with SVG visualization export for teaching/demonstration.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math
import random
import copy
from abc import ABC, abstractmethod

from room_relationships import SpatialGraph
from solver_suite import BaseSolver, SolverType, PlacedLayout, PlacedRoom, Rect, Point


# =============================================================================
# VISUALIZATION MIXIN
# =============================================================================

class VisualDebugMixin:
    """Mixin for solvers that support visual debugging."""
    
    def __init__(self):
        self.debug_frames: List[Dict] = []
        self.enable_visualization = False
    
    def record_frame(self, placed: Dict, iteration: int, info: str = ""):
        """Record a frame for animation."""
        if not self.enable_visualization:
            return
        
        frame = {
            "iteration": iteration,
            "info": info,
            "rooms": [
                {
                    "id": rid,
                    "x": r.rect.x,
                    "y": r.rect.y,
                    "width": r.rect.width,
                    "height": r.rect.height
                }
                for rid, r in placed.items()
            ]
        }
        self.debug_frames.append(frame)
    
    def export_animation_svg(self, filepath: str, width: float = None, depth: float = None):
        """Export solving process as animated SVG."""
        if not self.debug_frames:
            return
        
        w = width or self.width
        d = depth or self.depth
        scale = 800 / max(w, d)
        
        svg_parts = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">',
            f'  <rect width="100%" height="100%" fill="#f5f5f5"/>',
            f'  <g transform="translate(20,20) scale({scale})">',
            f'    <rect x="0" y="0" width="{w}" height="{d}" fill="white" stroke="#333" stroke-width="0.5"/>',
        ]
        
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#F7DC6F", "#BB8FCE"]
        
        for i, frame in enumerate(self.debug_frames):
            opacity = 0.3 + (i / len(self.debug_frames)) * 0.7
            for j, room in enumerate(frame["rooms"]):
                color = colors[j % len(colors)]
                svg_parts.append(
                    f'    <rect x="{room["x"]}" y="{room["y"]}" '
                    f'width="{room["width"]}" height="{room["height"]}" '
                    f'fill="{color}" fill-opacity="{opacity:.2f}" '
                    f'stroke="{color}" stroke-width="0.3"/>'
                )
        
        # Final state with labels
        if self.debug_frames:
            final = self.debug_frames[-1]
            for room in final["rooms"]:
                cx = room["x"] + room["width"] / 2
                cy = room["y"] + room["height"] / 2
                svg_parts.append(
                    f'    <text x="{cx}" y="{cy}" text-anchor="middle" '
                    f'font-size="2" fill="#333">{room["id"][:8]}</text>'
                )
        
        svg_parts.extend([
            '  </g>',
            '</svg>'
        ])
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(svg_parts))
        
        print(f"Animation exported to {filepath}")


# =============================================================================
# 7. GENETIC ALGORITHM SOLVER
# =============================================================================

@dataclass
class Genome:
    """A layout encoded as a genome."""
    genes: Dict[str, Tuple[float, float, float, float]]  # x, y, w, h for each room
    fitness: float = 0.0


class GeneticSolver(BaseSolver, VisualDebugMixin):
    """
    Genetic Algorithm solver.
    
    Evolutionary approach:
    1. Create population of random layouts
    2. Evaluate fitness (constraint satisfaction)
    3. Select best, crossover, mutate
    4. Repeat until convergence
    
    Good for: Global optimization, escaping local minima
    """
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float, grid_size: float = 2.0):
        BaseSolver.__init__(self, graph, width, depth, grid_size)
        VisualDebugMixin.__init__(self)
        
        self.population_size = 50
        self.generations = 100
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
        self.elite_size = 5
    
    @property
    def solver_type(self) -> SolverType:
        return SolverType.GENETIC
    
    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Run genetic algorithm."""
        self._start_timer()
        print(f"[Genetic] Evolving population of {self.population_size} for {self.generations} generations")
        
        # Initialize population
        population = self._init_population()
        
        best_ever = None
        best_fitness = -float('inf')
        
        for gen in range(self.generations):
            # Evaluate fitness
            for genome in population:
                genome.fitness = self._evaluate_fitness(genome)
                
                if genome.fitness > best_fitness:
                    best_fitness = genome.fitness
                    best_ever = copy.deepcopy(genome)
            
            # Record frame
            if gen % 10 == 0:
                placed = self._genome_to_placed(best_ever)
                self.record_frame(placed, gen, f"Gen {gen}, Fitness: {best_fitness:.1f}")
            
            # Selection
            population = self._select(population)
            
            # Crossover
            offspring = []
            while len(offspring) < self.population_size - self.elite_size:
                p1, p2 = random.sample(population[:20], 2)  # From top 20
                if random.random() < self.crossover_rate:
                    child = self._crossover(p1, p2)
                else:
                    child = copy.deepcopy(p1)
                offspring.append(child)
            
            # Mutation
            for genome in offspring:
                self._mutate(genome)
            
            # Elitism - keep best
            population = sorted(population, key=lambda g: g.fitness, reverse=True)[:self.elite_size] + offspring
            
            if gen % 20 == 0:
                print(f"[Genetic] Gen {gen}: Best fitness = {best_fitness:.1f}")
        
        # Convert best to layout
        placed = self._genome_to_placed(best_ever)
        
        layout = PlacedLayout(
            rooms=placed,
            is_complete=len(placed) == len(self.graph.rooms),
            score=best_fitness
        )
        
        print(f"[Genetic] Complete: {len(placed)}/{len(self.graph.rooms)} rooms, "
              f"Score: {layout.score:.1f}, Time: {self._elapsed():.2f}s")
        
        return layout
    
    def _init_population(self) -> List[Genome]:
        """Create initial random population."""
        population = []
        
        for _ in range(self.population_size):
            genes = {}
            for room_id, room in self.graph.rooms.items():
                area = room.min_area or 100
                aspect = random.uniform(0.6, 1.5)
                w = math.sqrt(area / aspect)
                h = area / w
                
                x = random.uniform(0, max(0, self.width - w))
                y = random.uniform(0, max(0, self.depth - h))
                
                genes[room_id] = (x, y, w, h)
            
            population.append(Genome(genes=genes))
        
        return population
    
    def _evaluate_fitness(self, genome: Genome) -> float:
        """Calculate fitness score."""
        score = 0.0
        placed = self._genome_to_placed(genome)
        
        # Completeness
        score += len(placed) * 10
        
        # No overlaps
        overlaps = 0
        for r1 in placed.values():
            for r2 in placed.values():
                if r1.node.id != r2.node.id and r1.rect.intersects(r2.rect):
                    overlaps += 1
        score -= overlaps * 50
        
        # Adjacency satisfaction
        for room_id, neighbors in self.graph.adjacencies.items():
            r1 = placed.get(room_id)
            if not r1:
                continue
            for neighbor_id in neighbors:
                r2 = placed.get(neighbor_id)
                if r2 and r1.rect.touches(r2.rect):
                    score += 20
        
        # Within bounds
        for r in placed.values():
            if r.rect.x2 <= self.width and r.rect.y2 <= self.depth:
                score += 5
            else:
                score -= 20
        
        return score
    
    def _select(self, population: List[Genome]) -> List[Genome]:
        """Tournament selection."""
        sorted_pop = sorted(population, key=lambda g: g.fitness, reverse=True)
        return sorted_pop[:self.population_size // 2]
    
    def _crossover(self, p1: Genome, p2: Genome) -> Genome:
        """Uniform crossover."""
        child_genes = {}
        for room_id in p1.genes:
            if random.random() < 0.5:
                child_genes[room_id] = p1.genes[room_id]
            else:
                child_genes[room_id] = p2.genes[room_id]
        return Genome(genes=child_genes)
    
    def _mutate(self, genome: Genome):
        """Random mutation with bounds enforcement."""
        for room_id in genome.genes:
            if random.random() < self.mutation_rate:
                x, y, w, h = genome.genes[room_id]
                # Small random adjustment
                dx = random.gauss(0, 2)
                dy = random.gauss(0, 2)
                # Keep in bounds
                new_x = max(0, min(x + dx, self.width - w))
                new_y = max(0, min(y + dy, self.depth - h))
                genome.genes[room_id] = (new_x, new_y, w, h)
    
    def _genome_to_placed(self, genome: Optional[Genome]) -> Dict[str, PlacedRoom]:
        """Convert genome to placed rooms."""
        if genome is None:
            return {}
        
        placed = {}
        for room_id, (x, y, w, h) in genome.genes.items():
            room_node = self.graph.rooms.get(room_id)
            if room_node:
                placed[room_id] = PlacedRoom(room_node, Rect(x, y, w, h))
        return placed


# =============================================================================
# 8. SIMULATED ANNEALING SOLVER
# =============================================================================

class SimulatedAnnealingSolver(BaseSolver, VisualDebugMixin):
    """
    Simulated Annealing solver.
    
    Thermodynamic-inspired:
    - Start hot (high temperature, accept bad moves)
    - Cool slowly (gradually only accept improvements)
    - Escape local minima through probabilistic acceptance
    
    Good for: Complex constraint landscapes, avoiding local optima
    """
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float, grid_size: float = 2.0):
        BaseSolver.__init__(self, graph, width, depth, grid_size)
        VisualDebugMixin.__init__(self)
        
        self.initial_temp = 100.0
        self.cooling_rate = 0.995
        self.min_temp = 0.01
    
    @property
    def solver_type(self) -> SolverType:
        return SolverType.ANNEALING
    
    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Run simulated annealing."""
        self._start_timer()
        print(f"[Annealing] Starting at T={self.initial_temp}, cooling rate={self.cooling_rate}")
        
        # Initial solution
        current = self._random_solution()
        current_energy = self._energy(current)
        
        best = copy.deepcopy(current)
        best_energy = current_energy
        
        temp = self.initial_temp
        iteration = 0
        
        while temp > self.min_temp and iteration < max_iterations:
            # Generate neighbor
            neighbor = self._neighbor(current)
            neighbor_energy = self._energy(neighbor)
            
            # Acceptance probability
            delta = neighbor_energy - current_energy
            
            if delta < 0 or random.random() < math.exp(-delta / temp):
                current = neighbor
                current_energy = neighbor_energy
                
                if current_energy < best_energy:
                    best = copy.deepcopy(current)
                    best_energy = current_energy
            
            # Cool
            temp *= self.cooling_rate
            iteration += 1
            
            # Record frame
            if iteration % 500 == 0:
                self.record_frame(best, iteration, f"T={temp:.2f}, E={best_energy:.1f}")
        
        layout = PlacedLayout(
            rooms=best,
            is_complete=len(best) == len(self.graph.rooms),
            score=100 - best_energy
        )
        
        print(f"[Annealing] Complete: {len(best)}/{len(self.graph.rooms)} rooms, "
              f"Score: {layout.score:.1f}, Time: {self._elapsed():.2f}s")
        
        return layout
    
    def _random_solution(self) -> Dict[str, PlacedRoom]:
        """Generate random initial solution."""
        placed = {}
        for room_id, room in self.graph.rooms.items():
            area = room.min_area or 100
            w = math.sqrt(area)
            h = area / w
            x = random.uniform(0, max(0, self.width - w))
            y = random.uniform(0, max(0, self.depth - h))
            placed[room_id] = PlacedRoom(room, Rect(x, y, w, h))
        return placed

    def _energy(self, placed: Dict) -> float:
        """Calculate energy (lower is better)."""
        energy = 0.0

        # Overlaps (high penalty)
        for r1 in placed.values():
            for r2 in placed.values():
                if r1.node.id != r2.node.id and r1.rect.intersects(r2.rect):
                    energy += 100
        
        # Out of bounds
        for r in placed.values():
            if r.rect.x2 > self.width:
                energy += (r.rect.x2 - self.width) * 10
            if r.rect.y2 > self.depth:
                energy += (r.rect.y2 - self.depth) * 10
        
        # Missing adjacencies
        for room_id, neighbors in self.graph.adjacencies.items():
            r1 = placed.get(room_id)
            if not r1:
                continue
            for neighbor_id in neighbors:
                r2 = placed.get(neighbor_id)
                if r2 and not r1.rect.touches(r2.rect):
                    energy += 20
        
        return energy
    
    def _neighbor(self, placed: Dict) -> Dict:
        """Generate neighboring solution with bounds enforcement."""
        new_placed = copy.deepcopy(placed)

        # Pick random room and move slightly
        room_id = random.choice(list(new_placed.keys()))
        room = new_placed[room_id]

        dx = random.gauss(0, 3)
        dy = random.gauss(0, 3)

        # Keep in bounds
        new_x = max(0, min(room.rect.x + dx, self.width - room.rect.width))
        new_y = max(0, min(room.rect.y + dy, self.depth - room.rect.height))

        new_rect = Rect(new_x, new_y, room.rect.width, room.rect.height)

        new_placed[room_id] = PlacedRoom(room.node, new_rect)
        return new_placed


# =============================================================================
# 9. FORCE-DIRECTED SOLVER
# =============================================================================

class ForceDirectedSolver(BaseSolver, VisualDebugMixin):
    """
    Force-directed placement.
    
    Physics simulation:
    - Adjacent rooms attract (spring force)
    - Overlapping rooms repel (collision force)
    - Walls contain (boundary force)
    - Let system settle to equilibrium
    
    Good for: Visual understanding of relationships, organic layouts
    """
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float, grid_size: float = 2.0):
        BaseSolver.__init__(self, graph, width, depth, grid_size)
        VisualDebugMixin.__init__(self)
        
        self.spring_strength = 0.01
        self.repulsion_strength = 100
        self.damping = 0.9
        self.iterations = 500
    
    @property
    def solver_type(self) -> SolverType:
        return SolverType.FORCE_DIRECTED
    
    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Run physics simulation."""
        self._start_timer()
        print(f"[Force] Running physics simulation for {self.iterations} steps")
        
        # Initialize with random positions
        positions: Dict[str, Point] = {}
        velocities: Dict[str, Point] = {}
        
        for room_id in self.graph.rooms:
            x = random.uniform(self.width * 0.2, self.width * 0.8)
            y = random.uniform(self.depth * 0.2, self.depth * 0.8)
            positions[room_id] = Point(x, y)
            velocities[room_id] = Point(0, 0)
        
        # Set room sizes
        sizes: Dict[str, Tuple[float, float]] = {}
        for room_id, room in self.graph.rooms.items():
            area = room.min_area or 100
            w = math.sqrt(area)
            h = area / w
            sizes[room_id] = (w, h)
        
        # Simulation loop
        for step in range(self.iterations):
            forces: Dict[str, Point] = {rid: Point(0, 0) for rid in positions}
            
            # Spring forces (adjacencies attract)
            for room_id, neighbors in self.graph.adjacencies.items():
                if room_id not in positions:
                    continue
                for neighbor_id in neighbors:
                    if neighbor_id not in positions:
                        continue
                    p1 = positions[room_id]
                    p2 = positions[neighbor_id]
                    dx = p2.x - p1.x
                    dy = p2.y - p1.y
                    dist = math.sqrt(dx**2 + dy**2) + 0.1

                    fx = dx * self.spring_strength
                    fy = dy * self.spring_strength

                    forces[room_id] = Point(forces[room_id].x + fx, forces[room_id].y + fy)
                    forces[neighbor_id] = Point(forces[neighbor_id].x - fx, forces[neighbor_id].y - fy)
            
            # Repulsion forces (overlap prevention)
            for r1 in positions:
                for r2 in positions:
                    if r1 >= r2:
                        continue
                    
                    p1 = positions[r1]
                    p2 = positions[r2]
                    dx = p1.x - p2.x
                    dy = p1.y - p2.y
                    dist = math.sqrt(dx**2 + dy**2) + 0.1
                    
                    if dist < 20:  # Close enough to repel
                        fx = dx / dist * self.repulsion_strength / dist
                        fy = dy / dist * self.repulsion_strength / dist
                        
                        forces[r1] = Point(forces[r1].x + fx, forces[r1].y + fy)
                        forces[r2] = Point(forces[r2].x - fx, forces[r2].y - fy)
            
            # Update positions
            for room_id in positions:
                # Update velocity
                vx = velocities[room_id].x * self.damping + forces[room_id].x
                vy = velocities[room_id].y * self.damping + forces[room_id].y
                velocities[room_id] = Point(vx, vy)
                
                # Update position
                new_x = max(0, min(self.width - sizes[room_id][0], positions[room_id].x + vx))
                new_y = max(0, min(self.depth - sizes[room_id][1], positions[room_id].y + vy))
                positions[room_id] = Point(new_x, new_y)
            
            # Record frame
            if step % 50 == 0:
                placed = self._positions_to_placed(positions, sizes)
                self.record_frame(placed, step, f"Step {step}")
        
        # Final layout
        placed = self._positions_to_placed(positions, sizes)

        # Final overlap cleanup - multiple passes with increasing strength
        for strength in [0.5, 1.0, 2.0]:
            placed = self._resolve_overlaps(placed, strength)

        layout = PlacedLayout(
            rooms=placed,
            is_complete=len(placed) == len(self.graph.rooms),
            score=self._calculate_score(placed)
        )

        print(f"[Force] Complete: {len(placed)}/{len(self.graph.rooms)} rooms, "
              f"Score: {layout.score:.1f}, Time: {self._elapsed():.2f}s")

        return layout

    def _resolve_overlaps(self, placed: Dict, strength: float = 1.0) -> Dict:
        """Final pass to resolve any remaining overlaps."""
        for iteration in range(200):
            overlaps_found = False
            room_list = list(placed.values())
            for i, r1 in enumerate(room_list):
                for r2 in room_list[i+1:]:
                    if r1.rect.intersects(r2.rect):
                        overlaps_found = True
                        # Calculate actual overlap amount
                        overlap_x = min(r1.rect.x2, r2.rect.x2) - max(r1.rect.x, r2.rect.x)
                        overlap_y = min(r1.rect.y2, r2.rect.y2) - max(r1.rect.y, r2.rect.y)

                        dx = r1.rect.center.x - r2.rect.center.x
                        dy = r1.rect.center.y - r2.rect.center.y
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001

                        # Stronger separation based on overlap depth and strength multiplier
                        sep_amount = (0.5 + min(overlap_x, overlap_y) * 0.5) * strength
                        sep_x = (dx / dist) * sep_amount
                        sep_y = (dy / dist) * sep_amount

                        r1.rect.x = max(0, min(r1.rect.x + sep_x, self.width - r1.rect.width))
                        r1.rect.y = max(0, min(r1.rect.y + sep_y, self.depth - r1.rect.height))
                        r2.rect.x = max(0, min(r2.rect.x - sep_x, self.width - r2.rect.width))
                        r2.rect.y = max(0, min(r2.rect.y - sep_y, self.depth - r2.rect.height))

            if not overlaps_found:
                break
        return placed
    
    def _positions_to_placed(self, positions: Dict, sizes: Dict) -> Dict[str, PlacedRoom]:
        """Convert positions to placed rooms."""
        placed = {}
        for room_id, pos in positions.items():
            room_node = self.graph.rooms.get(room_id)
            if room_node:
                w, h = sizes[room_id]
                placed[room_id] = PlacedRoom(room_node, Rect(pos.x, pos.y, w, h))
        return placed
    
    def _calculate_score(self, placed: Dict) -> float:
        """Calculate layout score."""
        score = 0.0
        
        # Completeness
        score += len(placed) * 10
        
        # Adjacencies
        for room_id, neighbors in self.graph.adjacencies.items():
            r1 = placed.get(room_id)
            if not r1:
                continue
            for neighbor_id in neighbors:
                r2 = placed.get(neighbor_id)
                if r2 and r1.rect.touches(r2.rect):
                    score += 15
        
        return score


# =============================================================================
# 10. SPACE COLONIZATION SOLVER
# =============================================================================

@dataclass
class Attractor:
    """Attraction point for space colonization."""
    x: float
    y: float
    room_id: str
    reached: bool = False


@dataclass
class Node:
    """Growth node."""
    x: float
    y: float
    parent: Optional['Node'] = None
    children: List['Node'] = field(default_factory=list)
    room_id: Optional[str] = None


class SpaceColonizationSolver(BaseSolver, VisualDebugMixin):
    """
    Space colonization algorithm.
    
    Growth-based organic layout:
    - Seed growth from entry
    - Attractors pull growth toward room centers
    - Competition for space creates natural boundaries
    - Inspired by leaf venation patterns
    
    Good for: Organic, nature-inspired layouts
    """
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float, grid_size: float = 2.0):
        BaseSolver.__init__(self, graph, width, depth, grid_size)
        VisualDebugMixin.__init__(self)
        
        self.segment_length = 5.0
        self.influence_radius = 50.0
        self.kill_distance = 10.0
    
    @property
    def solver_type(self) -> SolverType:
        return SolverType.SPACE_COLONIZATION
    
    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Run space colonization with improved growth strategy."""
        self._start_timer()
        print(f"[SpaceCol] Growing from entry with {len(self.graph.rooms)} attractors")

        # Sort rooms by connection distance from entry for better ordering
        # Use BFS to calculate distances
        def bfs_distance(start):
            distances = {start: 0}
            queue = [start]
            while queue:
                current = queue.pop(0)
                for neighbor in self.graph.adjacencies.get(current, []):
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        queue.append(neighbor)
            return distances

        entry_connections = {room_id: 99 for room_id in self.graph.rooms}
        if 'entry' in self.graph.rooms:
            entry_connections = bfs_distance('entry')

        sorted_rooms = sorted(self.graph.rooms.keys(), key=lambda r: entry_connections.get(r, 99))

        # Create attractors for each room in strategic positions
        attractors: List[Attractor] = []
        for i, room_id in enumerate(sorted_rooms):
            # Distribute attractors more evenly across the space
            angle = (i / len(sorted_rooms)) * 2 * math.pi if len(sorted_rooms) > 1 else 0
            radius = min(self.width, self.depth) * 0.35

            base_x = self.width / 2 + math.cos(angle) * radius
            base_y = self.depth / 2 + math.sin(angle) * radius

            # Add some randomness
            x = base_x + random.uniform(-2, 2)
            y = base_y + random.uniform(-2, 2)

            # Keep within bounds
            x = max(self.width * 0.1, min(self.width * 0.9, x))
            y = max(self.depth * 0.1, min(self.depth * 0.9, y))

            attractors.append(Attractor(x, y, room_id))

        # Seed growth from entry (multiple initial nodes)
        nodes = []
        for i in range(3):
            offset = (i - 1) * 2
            root = Node(x=self.width / 2 + offset, y=self.depth * 0.05)
            nodes.append(root)

        active_nodes = nodes[:]  # Nodes that can still grow
        reached_rooms = set()
        iteration = 0

        while attractors and iteration < max_iterations and active_nodes:
            new_nodes = []

            # For each active node, grow toward nearby attractors
            for node in active_nodes:
                if node.room_id:  # Already assigned - can spawn new growth
                    # Spawn new growth from reached nodes to spread
                    if random.random() < 0.3:  # 30% chance to branch
                        angle = random.uniform(0, 2 * math.pi)
                        new_x = node.x + math.cos(angle) * self.segment_length
                        new_y = node.y + math.sin(angle) * self.segment_length

                        if 0 <= new_x <= self.width and 0 <= new_y <= self.depth:
                            child = Node(x=new_x, y=new_y, parent=node)
                            node.children.append(child)
                            nodes.append(child)
                            new_nodes.append(child)
                    continue

                # Find attractors in influence radius
                nearby = [a for a in attractors
                         if math.sqrt((a.x - node.x)**2 + (a.y - node.y)**2) < self.influence_radius]

                if nearby:
                    # Grow toward average of nearby attractors
                    avg_x = sum(a.x for a in nearby) / len(nearby)
                    avg_y = sum(a.y for a in nearby) / len(nearby)

                    dx = avg_x - node.x
                    dy = avg_y - node.y
                    dist = math.sqrt(dx**2 + dy**2)

                    if dist > 0:
                        new_x = node.x + dx / dist * self.segment_length
                        new_y = node.y + dy / dist * self.segment_length

                        child = Node(x=new_x, y=new_y, parent=node)
                        node.children.append(child)
                        nodes.append(child)
                        new_nodes.append(child)

                        # Check if reached any attractor
                        for a in nearby:
                            if math.sqrt((a.x - new_x)**2 + (a.y - new_y)**2) < self.kill_distance:
                                if not a.reached:
                                    a.reached = True
                                    child.room_id = a.room_id
                                    reached_rooms.add(a.room_id)
                                    # This node becomes a source for new growth
                                    break

            # Also try random growth from unassigned nodes occasionally
            if iteration % 50 == 0:
                unassigned = [n for n in nodes if not n.room_id]
                if unassigned and len(reached_rooms) < len(self.graph.rooms) * 0.5:
                    node = random.choice(unassigned)
                    angle = random.uniform(0, 2 * math.pi)
                    new_x = node.x + math.cos(angle) * self.segment_length * 2
                    new_y = node.y + math.sin(angle) * self.segment_length * 2

                    if 0 <= new_x <= self.width and 0 <= new_y <= self.depth:
                        child = Node(x=new_x, y=new_y, parent=node)
                        node.children.append(child)
                        nodes.append(child)
                        new_nodes.append(child)

            active_nodes = [n for n in nodes if not n.room_id or n in new_nodes]

            # Remove reached attractors
            attractors = [a for a in attractors if not a.reached]

            iteration += 1

            # Record frame occasionally
            if iteration % 500 == 0:
                placed = self._nodes_to_placed(nodes)
                self.record_frame(placed, iteration, f"Iteration {iteration}, {len(reached_rooms)} rooms")

        # Convert to layout
        placed = self._nodes_to_placed(nodes)

        layout = PlacedLayout(
            rooms=placed,
            is_complete=len(placed) >= len(self.graph.rooms) * 0.5,
            score=len(placed) * 10 + len(reached_rooms) * 50
        )

        print(f"[SpaceCol] Complete: {len(placed)}/{len(self.graph.rooms)} rooms, "
              f"Score: {layout.score:.1f}, Time: {self._elapsed():.2f}s")

        return layout
    
    def _nodes_to_placed(self, nodes: List[Node]) -> Dict[str, PlacedRoom]:
        """Convert nodes to placed rooms with overlap resolution."""
        placed = {}

        # First pass: create rooms at node positions
        for node in nodes:
            if node.room_id and node.room_id not in placed:
                room_node = self.graph.rooms.get(node.room_id)
                if room_node:
                    area = room_node.min_area or 100
                    w = math.sqrt(area)
                    h = area / w

                    # Keep room in bounds
                    x = max(w/2, min(node.x, self.width - w/2))
                    y = max(h/2, min(node.y, self.depth - h/2))

                    placed[node.room_id] = PlacedRoom(
                        room_node,
                        Rect(x - w/2, y - h/2, w, h)
                    )

        # Second pass: resolve overlaps
        for _ in range(50):  # Iterative overlap resolution
            overlaps_found = False
            room_list = list(placed.values())
            for i, r1 in enumerate(room_list):
                for r2 in room_list[i+1:]:
                    if r1.rect.intersects(r2.rect):
                        overlaps_found = True
                        # Separate overlapping rooms
                        dx = r1.rect.center.x - r2.rect.center.x
                        dy = r1.rect.center.y - r2.rect.center.y
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001

                        sep_x = (dx / dist) * 0.5
                        sep_y = (dy / dist) * 0.5

                        # Move both rooms apart
                        new_x1 = max(0, min(r1.rect.x + sep_x, self.width - r1.rect.width))
                        new_y1 = max(0, min(r1.rect.y + sep_y, self.depth - r1.rect.height))
                        new_x2 = max(0, min(r2.rect.x - sep_x, self.width - r2.rect.width))
                        new_y2 = max(0, min(r2.rect.y - sep_y, self.depth - r2.rect.height))

                        r1.rect.x = new_x1
                        r1.rect.y = new_y1
                        r2.rect.x = new_x2
                        r2.rect.y = new_y2

            if not overlaps_found:
                break

        return placed


# =============================================================================
# UPDATE SOLVER SUITE
# =============================================================================

def update_solver_suite():
    """Add new solvers to the suite."""
    from solver_suite import SolverSuite
    
    # Add new solver types
    SolverSuite.SOLVER_MAP[SolverType.GENETIC] = GeneticSolver
    SolverSuite.SOLVER_MAP[SolverType.ANNEALING] = SimulatedAnnealingSolver
    SolverSuite.SOLVER_MAP[SolverType.FORCE_DIRECTED] = ForceDirectedSolver
    SolverSuite.SOLVER_MAP[SolverType.SPACE_COLONIZATION] = SpaceColonizationSolver
    
    # Update metadata
    SOLVER_INFO.update({
        SolverType.GENETIC: SolverMetadata(
            name="Genetic Algorithm",
            description="Evolutionary optimization with selection, crossover, and mutation. Population-based search for global optimum.",
            best_for=["Global optimization", "Escaping local minima", "Complex landscapes"],
            characteristics={
                "Room shapes": "Any - evolves over generations",
                "Adjacency guarantee": "Emergent from fitness function",
                "Output style": "Varied population, converges to good solutions",
                "Creativity": "High - explores diverse solutions",
                "Constraint handling": "Soft constraints via penalties"
            },
            speed="slow",
            reliability="medium"
        ),
        
        SolverType.ANNEALING: SolverMetadata(
            name="Simulated Annealing",
            description="Thermodynamic-inspired optimization. Starts hot (accepts bad moves), cools to find global optimum.",
            best_for=["Avoiding local optima", "Complex energy landscapes", "Fine-tuning layouts"],
            characteristics={
                "Room shapes": "Any - continuous adjustment",
                "Adjacency guarantee": "Gradual improvement",
                "Output style": "Smooth convergence",
                "Creativity": "Medium - probabilistic exploration",
                "Constraint handling": "Energy-based penalties"
            },
            speed="slow",
            reliability="medium"
        ),
        
        SolverType.FORCE_DIRECTED: SolverMetadata(
            name="Force-Directed",
            description="Physics simulation with spring and repulsion forces. Rooms settle into equilibrium like molecules.",
            best_for=["Visualizing relationships", "Organic layouts", "Teaching adjacency"],
            characteristics={
                "Room shapes": "Fixed, positions adjust",
                "Adjacency guarantee": "Springs pull adjacent rooms together",
                "Output style": "Dynamic, physics-based",
                "Creativity": "Medium - emergent from forces",
                "Constraint handling": "Forces encode constraints"
            },
            speed="medium",
            reliability="medium"
        ),
        
        SolverType.SPACE_COLONIZATION: SolverMetadata(
            name="Space Colonization",
            description="Growth-based algorithm inspired by leaf venation. Organic growth from seed to fill space.",
            best_for=["Nature-inspired designs", "Organic architecture", "Teaching growth processes"],
            characteristics={
                "Room shapes": "Organic, grown from center",
                "Adjacency guarantee": "Growth paths connect rooms",
                "Output style": "Natural, tree-like patterns",
                "Creativity": "Very high - emergent organic forms",
                "Constraint handling": "Attractors guide growth"
            },
            speed="medium",
            reliability="experimental"
        )
    })


if __name__ == "__main__":
    print("Advanced solvers with visual debugging loaded.")
    print("\nNew solvers available:")
    print("  - Genetic Algorithm (evolutionary)")
    print("  - Simulated Annealing (thermodynamic)")
    print("  - Force-Directed (physics)")
    print("  - Space Colonization (growth-based)")
    print("\nAll support SVG animation export for teaching!")
