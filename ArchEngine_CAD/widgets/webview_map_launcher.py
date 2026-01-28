#!/usr/bin/env python
"""
OpenStreetMap/Leaflet Map Launcher
==================================
Runs an interactive map using Leaflet.js and OpenStreetMap.
Uses Open Elevation API for terrain data.
"""

import sys
import argparse
import json
import os

try:
    import webview
except ImportError:
    print("Error: pywebview not installed. Run: pip install pywebview")
    sys.exit(1)

import requests


class MapAPI:
    """API class for JavaScript to call Python methods."""

    def __init__(self, output_file):
        self.output_file = output_file
        self.boundary_data = None

    def set_boundary(self, lat_min, lat_max, lng_min, lng_max, width_ft, depth_ft):
        """Called from JavaScript when boundary is drawn."""
        print("[Map] set_boundary called: %.0f' x %.0f'" % (width_ft, depth_ft))
        self.boundary_data = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lng_min': lng_min,
            'lng_max': lng_max,
            'width_ft': width_ft,
            'depth_ft': depth_ft
        }

        # Save immediately to ensure we don't lose the data
        try:
            with open(self.output_file, 'w') as f:
                json.dump({'boundary': self.boundary_data}, f)
                f.flush()
                os.fsync(f.fileno())
            print("[Map] Boundary saved immediately to %s" % self.output_file)
        except Exception as e:
            print("[Map] Error saving boundary: %s" % e)
            import traceback
            traceback.print_exc()

    def save_and_close(self):
        """Close the window (boundary already saved in set_boundary)."""
        print("[Map] save_and_close called")
        print("[Map] Closing window...")

        # Just close the window - boundary was already saved in set_boundary
        try:
            import sys
            sys.stdout.flush()
            # Use quit to trigger clean exit
            webview.api.exit()
        except:
            try:
                webview.destroy_window()
            except:
                pass

        # Force exit if webview exit doesn't work
        import sys
        import os
        print("[Map] Forcing exit...")
        sys.stdout.flush()
        os._exit(0)


def get_map_html(lat, lng, zoom):
    """Generate the Leaflet/OpenStreetMap HTML."""
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
        #map { width: 100vw; height: 100vh; }
        .controls {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            max-width: 320px;
        }
        .controls h3 { margin: 0 0 10px 0; font-size: 16px; color: #333; }
        .controls p { margin: 5px 0; font-size: 12px; color: #666; }
        .controls button {
            margin: 5px;
            padding: 10px 16px;
            cursor: pointer;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 13px;
        }
        .controls button:hover { background: #45a049; }
        .controls button.secondary { background: #6c757d; }
        .controls button.secondary:hover { background: #5a6268; }
        .controls button.success { background: #28a745; }
        .controls button.success:hover { background: #218838; }
        .info {
            position: absolute;
            bottom: 20px;
            left: 50%%;
            transform: translateX(-50%%);
            z-index: 1000;
            background: rgba(0,0,0,0.85);
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            font-size: 13px;
            max-width: 500px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="controls">
        <h3>Property Boundary Tool</h3>
        <p><strong>Instructions:</strong></p>
        <p>1. Pan and zoom to find your property</p>
        <p>2. Click "Start Drawing"</p>
        <p>3. Click points around your property</p>
        <p>4. Click "Finish" to complete</p>
        <p>5. Click "Save & Close" when done</p>
        <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
        <button onclick="startDrawing()">Start Drawing</button>
        <button onclick="finishPolygon()" class="secondary">Finish</button>
        <button onclick="clearBoundary()" class="secondary">Clear</button>
        <button onclick="saveAndClose()" class="success">Save & Close</button>
    </div>
    <div id="map"></div>
    <div class="info" id="info">Loading map...</div>

    <script>
        var map;
        var drawnItems;
        var polygonPoints = [];
        var polygon = null;
        var hasBoundary = false;
        var lat = %f;
        var lng = %f;
        var zoom = %d;

        // Initialize map
        function initMap() {
            // Create map centered on coordinates
            map = L.map('map').setView([lat, lng], zoom);

            // Add OpenStreetMap tile layer (free, no API key needed)
            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);

            // Add satellite layer (Esri World Imagery - free)
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri',
                maxZoom: 19
            }).addTo(map);

            // Initialize drawn items layer
            drawnItems = L.featureGroup().addTo(map);

            updateInfo('Map loaded! Click Start Drawing to begin');
        }

        function startDrawing() {
            if (polygon) {
                clearBoundary();
            }
            updateInfo('Click on map to place boundary points. Click Finish when done.');
            map.on('click', onMapClick);
            map.doubleClickZoom.disable();
        }

        function onMapClick(e) {
            var latlng = e.latlng;
            polygonPoints.push(latlng);

            // Add marker
            var marker = L.circleMarker(latlng, {
                radius: 5,
                fillColor: '#00FF00',
                fillOpacity: 0.8,
                color: '#FFFFFF',
                weight: 2
            }).addTo(drawnItems);

            // Update polygon if we have enough points
            if (polygonPoints.length >= 2) {
                if (polygon) {
                    drawnItems.removeLayer(polygon);
                }
                polygon = L.polygon(polygonPoints, {
                    color: '#00FF00',
                    fillColor: '#00FF00',
                    fillOpacity: 0.2,
                    weight: 3
                }).addTo(drawnItems);
            }

            updateInfo('Points: ' + polygonPoints.length + ' (click Finish when done)');
        }

        function finishPolygon() {
            if (polygonPoints.length < 3) {
                updateInfo('Need at least 3 points for a boundary!');
                return;
            }

            map.off('click', onMapClick);
            map.doubleClickZoom.enable();

            hasBoundary = true;

            // Get bounds
            var bounds = L.latLngBounds(polygonPoints);
            var latMin = bounds.getSouth();
            var latMax = bounds.getNorth();
            var lngMin = bounds.getWest();
            var lngMax = bounds.getEast();

            // Calculate approximate dimensions
            var latDiff = latMax - latMin;
            var lngDiff = lngMax - lngMin;
            var widthFt = Math.abs(latDiff) * 364000;
            var depthFt = Math.abs(lngDiff) * 364000 * 0.7071;
            var area = widthFt * depthFt;

            updateInfo('Property: ' + widthFt.toFixed(0) + "' x " + depthFt.toFixed(0) + "' = " + area.toFixed(0) + " sq ft - Click Save & Close");

            // Store boundary data
            window.boundaryData = {
                latMin: latMin,
                latMax: latMax,
                lngMin: lngMin,
                lngMax: lngMax,
                widthFt: widthFt,
                depthFt: depthFt
            };
        }

        function clearBoundary() {
            drawnItems.clearLayers();
            polygon = null;
            polygonPoints = [];
            hasBoundary = false;
            window.boundaryData = null;
            map.off('click', onMapClick);
            map.doubleClickZoom.enable();
            updateInfo('Boundary cleared. Click Start Drawing to begin.');
        }

        function saveAndClose() {
            if (!hasBoundary || !window.boundaryData) {
                updateInfo('Please draw a boundary first!');
                return;
            }

            var b = window.boundaryData;

            // Call Python API with boundary data
            if (pywebview && pywebview.api && pywebview.api.set_boundary) {
                pywebview.api.set_boundary(b.latMin, b.latMax, b.lngMin, b.lngMax, b.widthFt, b.depthFt);
                updateInfo('Boundary saved! Closing...');
                setTimeout(function() {
                    if (pywebview.api.save_and_close) {
                        pywebview.api.save_and_close();
                    } else {
                        window.close();
                    }
                }, 500);
            } else {
                updateInfo('Saving... (window will close automatically)');
                console.log('Boundary data:', b);
                // For testing - would normally save and close
                setTimeout(function() { window.close(); }, 1000);
            }
        }

        function updateInfo(text) {
            document.getElementById('info').textContent = text;
        }

        // Initialize on load
        window.onload = function() {
            initMap();
        };
    </script>
</body>
</html>""" % (lat, lng, zoom)

    return html


def main():
    parser = argparse.ArgumentParser(description='OpenStreetMap Launcher')
    parser.add_argument('--api-key', help='Not used - kept for compatibility')
    parser.add_argument('--lat', type=float, default=45.4215, help='Center latitude')
    parser.add_argument('--lng', type=float, default=-75.6972, help='Center longitude')
    parser.add_argument('--zoom', type=int, default=16, help='Zoom level')
    parser.add_argument('--output', required=True, help='Output JSON file for boundary data')

    args = parser.parse_args()

    print("[Map] Starting OpenStreetMap at (%f, %f), zoom %d" % (args.lat, args.lng, args.zoom))

    api = MapAPI(args.output)
    html_content = get_map_html(args.lat, args.lng, args.zoom)

    # Save HTML to file
    html_file = os.path.join(os.getcwd(), 'osm_map.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("[Map] HTML saved to: %s" % html_file)

    # Create window
    window = webview.create_window(
        title='Property Boundary Tool - OpenStreetMap',
        url='file:///' + html_file.replace(os.sep, "/"),
        js_api=api,
        width=1200,
        height=800,
        resizable=True,
        background_color='#1a1a1a'
    )

    webview.start(debug=False)


if __name__ == '__main__':
    main()
