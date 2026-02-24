"""
Benchmark Visualization

Generate charts and visual comparisons of solver performance.
"""

import json
from typing import Dict, List
from dataclasses import dataclass

def generate_comparison_chart(data: Dict, output_path: str = "benchmark_chart.svg"):
    """Generate SVG bar chart comparing solvers."""
    
    solvers = list(data.keys())
    scores = [data[s]["avg_score"] for s in solvers]
    times = [data[s]["avg_time_ms"] for s in solvers]
    
    # Normalize times for display (inverse, higher is better)
    max_time = max(times) if times else 1
    time_scores = [100 * (1 - t / max_time) for t in times]
    
    width = 800
    height = 400
    bar_width = 60
    spacing = 100
    
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4CAF50"/>
      <stop offset="100%" style="stop-color:#2E7D32"/>
    </linearGradient>
    <linearGradient id="timeGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#2196F3"/>
      <stop offset="100%" style="stop-color:#1565C0"/>
    </linearGradient>
  </defs>
  
  <rect width="100%" height="100%" fill="#f5f5f5"/>
  
  <text x="{width/2}" y="30" text-anchor="middle" font-size="20" font-weight="bold" fill="#333">
    Solver Performance Comparison
  </text>
'''
    
    # Draw bars
    start_x = 80
    max_bar_height = 250
    
    for i, solver in enumerate(solvers):
        x = start_x + i * spacing
        
        # Score bar
        score_height = (scores[i] / 100) * max_bar_height
        svg += f'''
  <rect x="{x}" y="{350 - score_height}" width="{bar_width/2 - 2}" height="{score_height}" 
        fill="url(#scoreGrad)" rx="4"/>
  <text x="{x + bar_width/4}" y="{340 - score_height}" text-anchor="middle" 
        font-size="12" font-weight="bold" fill="#2E7D32">{scores[i]:.0f}</text>
'''
        
        # Time bar
        time_height = (time_scores[i] / 100) * max_bar_height
        svg += f'''
  <rect x="{x + bar_width/2 + 2}" y="{350 - time_height}" width="{bar_width/2 - 2}" height="{time_height}" 
        fill="url(#timeGrad)" rx="4"/>
'''
        
        # Label
        svg += f'''
  <text x="{x + bar_width/2}" y="370" text-anchor="middle" font-size="11" fill="#555">{solver}</text>
'''
    
    # Legend
    svg += '''
  <rect x="550" y="80" width="15" height="15" fill="url(#scoreGrad)" rx="2"/>
  <text x="575" y="92" font-size="12" fill="#333">Overall Score</text>
  
  <rect x="550" y="105" width="15" height="15" fill="url(#timeGrad)" rx="2"/>
  <text x="575" y="117" font-size="12" fill="#333">Speed (inverse)</text>
'''
    
    svg += '</svg>'
    
    with open(output_path, 'w') as f:
        f.write(svg)
    
    print(f"Chart saved to {output_path}")


if __name__ == "__main__":
    # Example data
    example_data = {
        "grid": {"avg_score": 85, "avg_time_ms": 150},
        "wfc": {"avg_score": 72, "avg_time_ms": 400},
        "tree": {"avg_score": 78, "avg_time_ms": 200},
        "adj": {"avg_score": 90, "avg_time_ms": 600},
        "csp": {"avg_score": 65, "avg_time_ms": 800},
    }
    
    generate_comparison_chart(example_data)
