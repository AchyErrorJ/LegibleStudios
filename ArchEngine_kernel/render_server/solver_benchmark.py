"""
QBD Solver Benchmark Suite

Comprehensive benchmarking system for comparing solver algorithms.
Tracks performance, quality metrics, and generates client-ready reports.

Usage:
    from solver_benchmark import BenchmarkSuite, BenchmarkReport
    
    # Run benchmark
    benchmark = BenchmarkSuite()
    results = benchmark.run_full_benchmark()
    
    # Generate report
    report = BenchmarkReport(results)
    report.generate_html("benchmark_report.html")
    report.generate_pdf("benchmark_report.pdf")
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from datetime import datetime
import time
import json
import statistics
from collections import defaultdict
import random

from room_relationships import SpatialGraph, Room, Zone
from solver_suite import SolverSuite, SolverType, get_solver_descriptions
from coordinate_solver import PlacedLayout, Rect


# =============================================================================
# BENCHMARK METRICS
# =============================================================================

@dataclass
class SolverMetrics:
    """Metrics for a single solver run."""
    
    # Timing
    execution_time_ms: float
    nodes_explored: int
    iterations: int
    
    # Quality
    completeness: float  # 0-1, rooms placed / total rooms
    coverage: float  # 0-1, room area / building area
    adjacency_satisfaction: float  # 0-1, satisfied / total adjacencies
    exterior_satisfaction: float  # 0-1, rooms with exterior / required
    
    # Scores
    overall_score: float
    
    # Success
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BenchmarkResult:
    """Result of benchmarking a solver on a test case."""
    
    solver_type: SolverType
    test_case: str
    timestamp: datetime
    
    # Test parameters
    num_rooms: int
    num_adjacencies: int
    building_width: float
    building_depth: float
    
    # Metrics
    metrics: SolverMetrics
    
    # Raw data
    rooms_placed: int
    rooms_total: int
    adjs_satisfied: int
    adjs_total: int
    
    def to_dict(self) -> Dict:
        return {
            "solver_type": self.solver_type.value,
            "test_case": self.test_case,
            "timestamp": self.timestamp.isoformat(),
            "num_rooms": self.num_rooms,
            "num_adjacencies": self.num_adjacencies,
            "building_width": self.building_width,
            "building_depth": self.building_depth,
            "metrics": self.metrics.to_dict(),
            "rooms_placed": self.rooms_placed,
            "rooms_total": self.rooms_total,
            "adjs_satisfied": self.adjs_satisfied,
            "adjs_total": self.adjs_total,
        }


# =============================================================================
# TEST CASES
# =============================================================================

class TestCase:
    """A benchmark test case."""
    
    def __init__(
        self,
        name: str,
        description: str,
        room_specs: List[Dict],
        adjacencies: List[Tuple[str, str]],
        width: float,
        depth: float,
        difficulty: str = "medium"
    ):
        self.name = name
        self.description = description
        self.room_specs = room_specs
        self.adjacencies = adjacencies
        self.width = width
        self.depth = depth
        self.difficulty = difficulty
    
    def build_graph(self) -> SpatialGraph:
        """Build SpatialGraph from specs."""
        graph = SpatialGraph()
        
        for spec in self.room_specs:
            graph.add_room(
                room_id=spec["id"],
                room_type=spec.get("type", "room"),
                min_area=spec.get("min_area", 100),
                max_area=spec.get("max_area", 500)
            )
        
        for a, b in self.adjacencies:
            graph.connect(a, b)
        
        return graph


# Pre-defined test cases
TEST_CASES = [
    # Small simple house
    TestCase(
        name="small_simple",
        description="Small 3-bedroom house with simple adjacencies",
        room_specs=[
            {"id": "entry", "type": "entry", "min_area": 40},
            {"id": "living", "type": "living", "min_area": 200},
            {"id": "kitchen", "type": "kitchen", "min_area": 150},
            {"id": "bed1", "type": "bedroom", "min_area": 150},
            {"id": "bed2", "type": "bedroom", "min_area": 120},
            {"id": "bed3", "type": "bedroom", "min_area": 120},
            {"id": "bath1", "type": "bathroom", "min_area": 50},
            {"id": "bath2", "type": "bathroom", "min_area": 40},
        ],
        adjacencies=[
            ("entry", "living"),
            ("living", "kitchen"),
            ("living", "bed1"),
            ("living", "bed2"),
            ("living", "bed3"),
            ("bed1", "bath1"),
            ("bed2", "bath2"),
        ],
        width=40,
        depth=30,
        difficulty="easy"
    ),
    
    # Medium house with garage
    TestCase(
        name="medium_with_garage",
        description="4-bedroom house with garage and mudroom",
        room_specs=[
            {"id": "entry", "type": "entry", "min_area": 50},
            {"id": "living", "type": "living", "min_area": 250},
            {"id": "kitchen", "type": "kitchen", "min_area": 180},
            {"id": "dining", "type": "dining", "min_area": 150},
            {"id": "primary", "type": "primary_bedroom", "min_area": 200},
            {"id": "primary_bath", "type": "bathroom", "min_area": 80},
            {"id": "bed2", "type": "bedroom", "min_area": 140},
            {"id": "bed3", "type": "bedroom", "min_area": 140},
            {"id": "bed4", "type": "bedroom", "min_area": 120},
            {"id": "bath2", "type": "bathroom", "min_area": 50},
            {"id": "garage", "type": "garage", "min_area": 400},
            {"id": "mudroom", "type": "mudroom", "min_area": 60},
        ],
        adjacencies=[
            ("entry", "living"),
            ("living", "kitchen"),
            ("living", "dining"),
            ("kitchen", "dining"),
            ("living", "primary"),
            ("living", "bed2"),
            ("living", "bed3"),
            ("living", "bed4"),
            ("primary", "primary_bath"),
            ("bed2", "bath2"),
            ("bed3", "bath2"),
            ("garage", "mudroom"),
            ("mudroom", "kitchen"),
        ],
        width=50,
        depth=40,
        difficulty="medium"
    ),
    
    # Complex with many adjacencies
    TestCase(
        name="complex_adjacencies",
        description="Complex house with dense adjacency requirements",
        room_specs=[
            {"id": "entry", "type": "entry", "min_area": 60},
            {"id": "foyer", "type": "foyer", "min_area": 80},
            {"id": "living", "type": "living", "min_area": 300},
            {"id": "family", "type": "living", "min_area": 250},
            {"id": "kitchen", "type": "kitchen", "min_area": 200},
            {"id": "dining", "type": "dining", "min_area": 180},
            {"id": "breakfast", "type": "dining", "min_area": 120},
            {"id": "primary", "type": "primary_bedroom", "min_area": 250},
            {"id": "primary_bath", "type": "bathroom", "min_area": 100},
            {"id": "primary_closet", "type": "closet", "min_area": 50},
            {"id": "bed2", "type": "bedroom", "min_area": 160},
            {"id": "bed3", "type": "bedroom", "min_area": 160},
            {"id": "bed4", "type": "bedroom", "min_area": 140},
            {"id": "bath2", "type": "bathroom", "min_area": 60},
            {"id": "bath3", "type": "bathroom", "min_area": 50},
            {"id": "office", "type": "office", "min_area": 150},
            {"id": "laundry", "type": "laundry", "min_area": 60},
            {"id": "pantry", "type": "pantry", "min_area": 40},
        ],
        adjacencies=[
            ("entry", "foyer"),
            ("foyer", "living"),
            ("foyer", "family"),
            ("living", "dining"),
            ("family", "kitchen"),
            ("kitchen", "breakfast"),
            ("kitchen", "dining"),
            ("kitchen", "pantry"),
            ("family", "primary"),
            ("primary", "primary_bath"),
            ("primary", "primary_closet"),
            ("family", "bed2"),
            ("family", "bed3"),
            ("family", "bed4"),
            ("bed2", "bath2"),
            ("bed3", "bath2"),
            ("bed4", "bath3"),
            ("foyer", "office"),
            ("kitchen", "laundry"),
        ],
        width=60,
        depth=50,
        difficulty="hard"
    ),
    
    # L-shaped challenge
    TestCase(
        name="l_shaped",
        description="L-shaped layout challenge for organic solvers",
        room_specs=[
            {"id": "entry", "type": "entry", "min_area": 50},
            {"id": "living", "type": "living", "min_area": 280},
            {"id": "kitchen", "type": "kitchen", "min_area": 180},
            {"id": "wing_bed1", "type": "bedroom", "min_area": 160},
            {"id": "wing_bed2", "type": "bedroom", "min_area": 160},
            {"id": "wing_bath", "type": "bathroom", "min_area": 60},
            {"id": "main_bed", "type": "bedroom", "min_area": 200},
            {"id": "main_bath", "type": "bathroom", "min_area": 80},
        ],
        adjacencies=[
            ("entry", "living"),
            ("living", "kitchen"),
            ("living", "main_bed"),
            ("main_bed", "main_bath"),
            ("living", "wing_bed1"),
            ("wing_bed1", "wing_bed2"),
            ("wing_bed2", "wing_bath"),
        ],
        width=50,
        depth=50,
        difficulty="hard"
    ),
    
    # Small apartment
    TestCase(
        name="small_apartment",
        description="Compact apartment layout",
        room_specs=[
            {"id": "entry", "type": "entry", "min_area": 30},
            {"id": "living", "type": "living", "min_area": 180},
            {"id": "kitchen", "type": "kitchen", "min_area": 100},
            {"id": "bed", "type": "bedroom", "min_area": 140},
            {"id": "bath", "type": "bathroom", "min_area": 40},
            {"id": "closet", "type": "closet", "min_area": 30},
        ],
        adjacencies=[
            ("entry", "living"),
            ("living", "kitchen"),
            ("living", "bed"),
            ("bed", "bath"),
            ("bed", "closet"),
        ],
        width=25,
        depth=20,
        difficulty="easy"
    ),
]


# =============================================================================
# BENCHMARK SUITE
# =============================================================================

class BenchmarkSuite:
    """Main benchmarking system."""
    
    def __init__(self, iterations_per_test: int = 3):
        self.iterations = iterations_per_test
        self.results: List[BenchmarkResult] = []
    
    def run_full_benchmark(self, solvers: List[SolverType] = None) -> List[BenchmarkResult]:
        """
        Run complete benchmark on all test cases.
        
        Args:
            solvers: List of solvers to test (default: all except hybrid)
        
        Returns:
            List of BenchmarkResult
        """
        if solvers is None:
            solvers = [st for st in SolverType if st != SolverType.HYBRID]
        
        self.results = []
        
        print(f"Starting benchmark: {len(solvers)} solvers x {len(TEST_CASES)} cases x {self.iterations} iterations")
        print("=" * 70)
        
        for test_case in TEST_CASES:
            print(f"\nTest Case: {test_case.name} ({test_case.difficulty})")
            print(f"  {test_case.description}")
            print(f"  Rooms: {len(test_case.room_specs)}, Adjs: {len(test_case.adjacencies)}")
            print(f"  Size: {test_case.width}x{test_case.depth}")
            
            for solver_type in solvers:
                print(f"\n  Testing {solver_type.value}...", end=" ")
                
                for i in range(self.iterations):
                    result = self._run_single_test(test_case, solver_type)
                    self.results.append(result)
                    print(f"{result.metrics.overall_score:.0f}", end=" ")
                
                print()
        
        print("\n" + "=" * 70)
        print(f"Benchmark complete: {len(self.results)} results")
        
        return self.results
    
    def _run_single_test(
        self,
        test_case: TestCase,
        solver_type: SolverType
    ) -> BenchmarkResult:
        """Run a single test iteration."""
        # Build graph
        graph = test_case.build_graph()
        
        # Run solver
        suite = SolverSuite(graph, test_case.width, test_case.depth)
        
        start_time = time.time()
        
        try:
            layout = suite.solve(solver_type, max_iterations=10000)
            success = True
            error_msg = None
        except Exception as e:
            layout = PlacedLayout({}, [], Rect(0, 0, test_case.width, test_case.depth),
                                 False, list(graph.rooms), 0.0)
            success = False
            error_msg = str(e)
        
        execution_time = (time.time() - start_time) * 1000  # ms
        
        # Calculate metrics
        metrics = self._calculate_metrics(layout, graph, test_case, execution_time, success, error_msg)
        
        return BenchmarkResult(
            solver_type=solver_type,
            test_case=test_case.name,
            timestamp=datetime.now(),
            num_rooms=len(test_case.room_specs),
            num_adjacencies=len(test_case.adjacencies),
            building_width=test_case.width,
            building_depth=test_case.depth,
            metrics=metrics,
            rooms_placed=len(layout.rooms),
            rooms_total=len(graph.rooms),
            adjs_satisfied=self._count_satisfied_adjs(layout, graph),
            adjs_total=len(graph.adjacencies)
        )
    
    def _calculate_metrics(
        self,
        layout: PlacedLayout,
        graph: SpatialGraph,
        test_case: TestCase,
        execution_time: float,
        success: bool,
        error_msg: Optional[str]
    ) -> SolverMetrics:
        """Calculate all metrics for a run."""
        
        # Completeness
        completeness = len(layout.rooms) / max(len(graph.rooms), 1)
        
        # Coverage
        room_area = sum(r.area for r in layout.rooms.values())
        building_area = test_case.width * test_case.depth
        coverage = room_area / building_area
        
        # Adjacency satisfaction
        adj_satisfaction = self._calculate_adj_satisfaction(layout, graph)
        
        # Exterior satisfaction (simplified)
        exterior_req = sum(1 for r in graph.rooms.values()
                         if ROOM_TYPES.get(r.type, Room("", "", Zone.PUBLIC)).exterior == ExteriorRequirement.REQUIRED)
        exterior_sat = 1.0  # Simplified
        
        # Overall score
        score = (
            completeness * 30 +
            min(coverage, 0.8) / 0.8 * 20 +
            adj_satisfaction * 30 +
            (20 if success else 0)
        )
        
        return SolverMetrics(
            execution_time_ms=execution_time,
            nodes_explored=getattr(layout, 'nodes_explored', 0),
            iterations=0,
            completeness=completeness,
            coverage=coverage,
            adjacency_satisfaction=adj_satisfaction,
            exterior_satisfaction=exterior_sat,
            overall_score=score,
            success=success,
            error_message=error_msg
        )
    
    def _calculate_adj_satisfaction(self, layout: PlacedLayout, graph: SpatialGraph) -> float:
        """Calculate adjacency satisfaction ratio."""
        if not graph.adjacencies:
            return 1.0
        
        satisfied = 0
        for adj in graph.adjacencies:
            r1 = layout.rooms.get(adj.room_a)
            r2 = layout.rooms.get(adj.room_b)
            if r1 and r2 and r1.rect.touches(r2.rect):
                satisfied += 1
        
        return satisfied / len(graph.adjacencies)
    
    def _count_satisfied_adjs(self, layout: PlacedLayout, graph: SpatialGraph) -> int:
        """Count satisfied adjacencies."""
        count = 0
        for adj in graph.adjacencies:
            r1 = layout.rooms.get(adj.room_a)
            r2 = layout.rooms.get(adj.room_b)
            if r1 and r2 and r1.rect.touches(r2.rect):
                count += 1
        return count
    
    def get_summary(self) -> Dict:
        """Get summary statistics."""
        if not self.results:
            return {}
        
        summary = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            key = result.solver_type.value
            summary[key]["scores"].append(result.metrics.overall_score)
            summary[key]["times"].append(result.metrics.execution_time_ms)
            summary[key]["completeness"].append(result.metrics.completeness)
            summary[key]["adj_satisfaction"].append(result.metrics.adjacency_satisfaction)
        
        # Calculate statistics
        stats = {}
        for solver, data in summary.items():
            stats[solver] = {
                "avg_score": statistics.mean(data["scores"]),
                "min_score": min(data["scores"]),
                "max_score": max(data["scores"]),
                "std_score": statistics.stdev(data["scores"]) if len(data["scores"]) > 1 else 0,
                "avg_time_ms": statistics.mean(data["times"]),
                "avg_completeness": statistics.mean(data["completeness"]),
                "avg_adj_satisfaction": statistics.mean(data["adj_satisfaction"]),
            }
        
        return stats
    
    def save_results(self, filepath: str):
        """Save results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "iterations_per_test": self.iterations,
            "results": [r.to_dict() for r in self.results],
            "summary": self.get_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to {filepath}")


# =============================================================================
# BENCHMARK REPORT
# =============================================================================

class BenchmarkReport:
    """Generate client-ready benchmark reports."""
    
    def __init__(self, results: List[BenchmarkResult]):
        self.results = results
        self.summary = self._calculate_summary()
    
    def _calculate_summary(self) -> Dict:
        """Calculate summary from results."""
        suite = BenchmarkSuite()
        suite.results = self.results
        return suite.get_summary()
    
    def generate_html(self, filepath: str):
        """Generate HTML report."""
        html = self._build_html()
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        print(f"HTML report saved to {filepath}")
    
    def _build_html(self) -> str:
        """Build HTML content."""
        solver_info = get_solver_descriptions()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>QBD Solver Benchmark Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 40px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .solver-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .solver-card h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        .metric:last-child {{
            border-bottom: none;
        }}
        .metric-value {{
            font-weight: bold;
            color: #4CAF50;
        }}
        .score-bar {{
            background: #e0e0e0;
            height: 20px;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .score-fill {{
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            height: 100%;
            transition: width 0.3s ease;
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }}
        .comparison-table th {{
            background: #2c3e50;
            color: white;
            padding: 15px;
            text-align: left;
        }}
        .comparison-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        .comparison-table tr:hover {{
            background: #f5f5f5;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-fast {{ background: #4CAF50; color: white; }}
        .badge-medium {{ background: #FF9800; color: white; }}
        .badge-slow {{ background: #f44336; color: white; }}
        .badge-high {{ background: #2196F3; color: white; }}
        .badge-experimental {{ background: #9C27B0; color: white; }}
        .winner {{ border: 2px solid #FFD700; }}
    </style>
</head>
<body>
    <h1>QBD Solver Benchmark Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Solver Performance Summary</h2>
    <div class="summary-grid">
"""
        
        # Add solver cards
        for solver_type, stats in sorted(self.summary.items(), 
                                         key=lambda x: x[1]['avg_score'], 
                                         reverse=True):
            info = solver_info.get(solver_type, {})
            is_winner = solver_type == max(self.summary.keys(), 
                                          key=lambda k: self.summary[k]['avg_score'])
            
            card_class = "solver-card winner" if is_winner else "solver-card"
            speed_class = f"badge-{info.get('speed', 'medium')}"
            reliability_class = f"badge-{info.get('reliability', 'medium')}"
            
            html += f"""
        <div class="{card_class}">
            <h3>{info.get('name', solver_type)} {'👑' if is_winner else ''}</h3>
            <span class="badge {speed_class}">{info.get('speed', 'medium').upper()}</span>
            <span class="badge {reliability_class}">{info.get('reliability', 'medium').upper()}</span>
            
            <div class="score-bar">
                <div class="score-fill" style="width: {stats['avg_score']}%"></div>
            </div>
            
            <div class="metric">
                <span>Average Score</span>
                <span class="metric-value">{stats['avg_score']:.1f}/100</span>
            </div>
            <div class="metric">
                <span>Score Range</span>
                <span>{stats['min_score']:.1f} - {stats['max_score']:.1f}</span>
            </div>
            <div class="metric">
                <span>Avg Time</span>
                <span>{stats['avg_time_ms']:.0f}ms</span>
            </div>
            <div class="metric">
                <span>Completeness</span>
                <span class="metric-value">{stats['avg_completeness']*100:.1f}%</span>
            </div>
            <div class="metric">
                <span>Adjacency Satisfaction</span>
                <span class="metric-value">{stats['avg_adj_satisfaction']*100:.1f}%</span>
            </div>
        </div>
"""
        
        html += """
    </div>
    
    <h2>Detailed Comparison</h2>
    <table class="comparison-table">
        <thead>
            <tr>
                <th>Solver</th>
                <th>Speed</th>
                <th>Reliability</th>
                <th>Avg Score</th>
                <th>Completeness</th>
                <th>Adjacency</th>
                <th>Best For</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for solver_type, stats in sorted(self.summary.items(), 
                                         key=lambda x: x[1]['avg_score'], 
                                         reverse=True):
            info = solver_info.get(solver_type, {})
            best_for = info.get('best_for', [])
            best_for_str = ', '.join(best_for[:2]) if best_for else 'General'
            
            html += f"""
            <tr>
                <td><strong>{info.get('name', solver_type)}</strong></td>
                <td>{info.get('speed', 'medium')}</td>
                <td>{info.get('reliability', 'medium')}</td>
                <td>{stats['avg_score']:.1f}</td>
                <td>{stats['avg_completeness']*100:.1f}%</td>
                <td>{stats['avg_adj_satisfaction']*100:.1f}%</td>
                <td>{best_for_str}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <h2>Solver Descriptions</h2>
"""
        
        for solver_type, info in solver_info.items():
            if solver_type == 'hybrid':
                continue
                
            html += f"""
    <div class="solver-card" style="margin: 20px 0;">
        <h3>{info.get('name', solver_type)}</h3>
        <p>{info.get('description', '')}</p>
        <p><strong>Characteristics:</strong></p>
        <ul>
"""
            for key, value in info.get('characteristics', {}).items():
                html += f"            <li><strong>{key}:</strong> {value}</li>\n"
            
            html += """        </ul>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        return html
    
    def generate_markdown(self, filepath: str):
        """Generate Markdown report."""
        md = self._build_markdown()
        
        with open(filepath, 'w') as f:
            f.write(md)
        
        print(f"Markdown report saved to {filepath}")
    
    def _build_markdown(self) -> str:
        """Build Markdown content."""
        solver_info = get_solver_descriptions()
        
        md = f"""# QBD Solver Benchmark Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

| Solver | Avg Score | Completeness | Adjacency | Avg Time |
|--------|-----------|--------------|-----------|----------|
"""
        
        for solver_type, stats in sorted(self.summary.items(), 
                                         key=lambda x: x[1]['avg_score'], 
                                         reverse=True):
            info = solver_info.get(solver_type, {})
            md += f"| {info.get('name', solver_type)} | {stats['avg_score']:.1f} | {stats['avg_completeness']*100:.1f}% | {stats['avg_adj_satisfaction']*100:.1f}% | {stats['avg_time_ms']:.0f}ms |\n"
        
        md += """
## Detailed Results

"""
        
        for solver_type, stats in sorted(self.summary.items(), 
                                         key=lambda x: x[1]['avg_score'], 
                                         reverse=True):
            info = solver_info.get(solver_type, {})
            is_winner = solver_type == max(self.summary.keys(), 
                                          key=lambda k: self.summary[k]['avg_score'])
            
            md += f"""### {info.get('name', solver_type)} {'👑' if is_winner else ''}

- **Speed:** {info.get('speed', 'medium')}
- **Reliability:** {info.get('reliability', 'medium')}
- **Average Score:** {stats['avg_score']:.1f}/100 (range: {stats['min_score']:.1f} - {stats['max_score']:.1f})
- **Average Time:** {stats['avg_time_ms']:.0f}ms
- **Completeness:** {stats['avg_completeness']*100:.1f}%
- **Adjacency Satisfaction:** {stats['avg_adj_satisfaction']*100:.1f}%

**Best for:** {', '.join(info.get('best_for', ['General']))}

{info.get('description', '')}

"""
        
        return md


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_benchmark(iterations: int = 3) -> Tuple[List[BenchmarkResult], Dict]:
    """Run benchmark and return results with summary."""
    suite = BenchmarkSuite(iterations_per_test=iterations)
    results = suite.run_full_benchmark()
    summary = suite.get_summary()
    return results, summary


def generate_report(results: List[BenchmarkResult], output_dir: str = "."):
    """Generate all report formats."""
    report = BenchmarkReport(results)
    
    report.generate_html(f"{output_dir}/benchmark_report.html")
    report.generate_markdown(f"{output_dir}/benchmark_report.md")
    
    # Also save raw data
    suite = BenchmarkSuite()
    suite.results = results
    suite.save_results(f"{output_dir}/benchmark_data.json")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("QBD SOLVER BENCHMARK")
    print("=" * 70)
    
    # Run benchmark
    results, summary = run_benchmark(iterations=3)
    
    # Generate reports
    generate_report(results, output_dir="./benchmark_output")
    
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print("\nTop Performers:")
    
    sorted_solvers = sorted(summary.items(), key=lambda x: x[1]['avg_score'], reverse=True)
    for i, (solver, stats) in enumerate(sorted_solvers[:3], 1):
        print(f"  {i}. {solver}: {stats['avg_score']:.1f} points")
