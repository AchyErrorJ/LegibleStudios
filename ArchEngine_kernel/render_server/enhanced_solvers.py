"""
Enhanced Coordinate Solvers for QBD Algebra
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math
import random
from collections import defaultdict, deque

from room_relationships import SpatialGraph
from coordinate_solver import Point, Rect, PlacedRoom, PlacedLayout


class WFCTile(Enum):
    EMPTY = 0
    ROOM = 1  
    WALL = 2
    DOOR = 3


@dataclass 
class WFCCell:
    x: int
    y: int
    possible: Set[WFCTile] = field(default_factory=lambda: set(WFCTile))
    collapsed: bool = False
    tile: Optional[WFCTile] = None


class WaveFunctionCollapseSolver:
    """WFC algorithm for organic floor plans."""
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float, tile_size: float = 2.0):
        self.graph = graph
        self.width = width
        self.depth = depth
        self.tile_size = tile_size
        self.gw = int(width / tile_size)
        self.gh = int(depth / tile_size)
        self.grid: Dict[Tuple[int,int], WFCCell] = {}
        for x in range(self.gw):
            for y in range(self.gh):
                c = WFCCell(x=x, y=y)
                if x==0 or x==self.gw-1 or y==0 or y==self.gh-1:
                    c.possible = {WFCTile.WALL}
                self.grid[(x,y)] = c
    
    def solve(self, max_iter: int = 10000) -> PlacedLayout:
        # Seed entry
        e = self.grid[(self.gw//2, 0)]
        e.collapsed = True
        e.tile = WFCTile.DOOR
        self._prop(e)
        
        for _ in range(max_iter):
            if self._done():
                break
            c = self._pick()
            if c is None:
                break
            self._collapse(c)
            self._prop(c)
        
        return self._layout()
    
    def _pick(self) -> Optional[WFCCell]:
        best, n = None, float('inf')
        for c in self.grid.values():
            if not c.collapsed and 0 < len(c.possible) < n:
                n = len(c.possible)
                best = c
        return best
    
    def _collapse(self, c: WFCCell):
        c.tile = random.choice(list(c.possible)) if c.possible else WFCTile.EMPTY
        c.collapsed = True
    
    def _prop(self, c: WFCCell):
        q = deque([c])
        while q:
            c = q.popleft()
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                n = self.grid.get((c.x+dx,c.y+dy))
                if n and not n.collapsed:
                    if c.tile == WFCTile.WALL and WFCTile.EMPTY in n.possible:
                        n.possible.discard(WFCTile.EMPTY)
                        q.append(n)
    
    def _done(self) -> bool:
        return all(c.collapsed for c in self.grid.values())
    
    def _layout(self) -> PlacedLayout:
        # Find ROOM regions
        regions = []
        seen = set()
        for (x,y),c in self.grid.items():
            if c.tile == WFCTile.ROOM and (x,y) not in seen:
                r = set()
                q = deque([(x,y)])
                while q:
                    cx,cy = q.popleft()
                    if (cx,cy) in seen:
                        continue
                    seen.add((cx,cy))
                    cell = self.grid.get((cx,cy))
                    if cell and cell.tile == WFCTile.ROOM:
                        r.add((cx,cy))
                        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                            q.append((cx+dx,cy+dy))
                regions.append(r)
        
        placed = {}
        rooms = list(self.graph.rooms.keys())
        for i,r in enumerate(regions):
            if i >= len(rooms):
                break
            xs,ys = [c[0] for c in r],[c[1] for c in r]
            rect = Rect(min(xs)*self.tile_size, min(ys)*self.tile_size,
                       (max(xs)-min(xs)+1)*self.tile_size, (max(ys)-min(ys)+1)*self.tile_size)
            placed[rooms[i]] = PlacedRoom(rooms[i], rect)
        
        return PlacedLayout(placed, [], Rect(0,0,self.width,self.depth),
                          len(placed) >= len(self.graph.rooms)*0.7,
                          [r for r in self.graph.rooms if r not in placed],
                          50.0 if placed else 0.0)


class HybridSolver:
    """Combines multiple solvers for best results."""
    
    def __init__(self, graph: SpatialGraph, width: float, depth: float):
        self.graph = graph
        self.width = width
        self.depth = depth
    
    def solve(self) -> PlacedLayout:
        """Try multiple solvers and return best result."""
        results = []
        
        # Try WFC
        try:
            wfc = WaveFunctionCollapseSolver(self.graph, self.width, self.depth)
            r = wfc.solve()
            if r.is_complete:
                results.append((r.score, r, "WFC"))
        except Exception as e:
            print(f"[Hybrid] WFC failed: {e}")
        
        # Could add more solvers here
        
        if results:
            results.sort(key=lambda x: x[0], reverse=True)
            print(f"[Hybrid] Best: {results[0][2]} with score {results[0][0]}")
            return results[0][1]
        
        # Fallback: return empty layout
        return PlacedLayout({}, [], Rect(0,0,self.width,self.depth), False,
                          list(self.graph.rooms), 0.0)
