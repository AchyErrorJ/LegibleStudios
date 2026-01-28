#!/usr/bin/env python
"""
OpenStreetMap/Leaflet Map Launcher (Browser Version)
=====================================================
Opens an interactive map using Leaflet.js and OpenStreetMap in the default browser.
"""

import sys
import argparse
import json
import os
import webbrowser
import http.server
import socketserver
import threading
from pathlib import Path


class MapHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for serving the map and receiving boundary data."""

    def do_GET(self):
        """Serve the map HTML."""
        if self.path == '/' or self.path == '/map':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            # Read lat/lng from server state
            lat = self.server.lat
            lng = self.server.lng
            zoom = self.server.zoom

            html = self.generate_map_html(lat, lng, zoom)
            self.wfile.write(html.encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        """Receive boundary data from the map."""
        if self.path == '/boundary':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            boundary_data = json.loads(post_data.decode('utf-8'))

            print("[Map] Boundary received: %.0f' x %.0f'" %
                  (boundary_data['width_ft'], boundary_data['depth_ft']))

            # Save to output file
            with open(self.server.output_file, 'w') as f:
                json.dump({'boundary': boundary_data}, f)

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

            # Shutdown server after receiving data
            threading.Timer(1.0, self.server.shutdown).start()

    def generate_map_html(self, lat, lng, zoom):
        """Generate the Leaflet/OpenStreetMap HTML."""
        return """<!DOCTYPE html>
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
        <p>5. Click "Save & Return" when done</p>
        <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
        <button onclick="startDrawing()">Start Drawing</button>
        <button onclick="finishPolygon()" class="secondary">Finish</button>
        <button onclick="clearBoundary()" class="secondary">Clear</button>
        <button onclick="saveAndReturn()" class="success">Save & Return</button>
    </div>
    <div id="map"></div>
    <div class="info" id="info">Loading map...</div>

    <script>
        var map;
        var drawnItems;
        var polygonPoints = [];
        var polygon = null;
        var hasBoundary = false;

        // Initialize map
        function initMap() {
            map = L.map('map').setView([""" + str(lat) + """, """ + str(lng) + """], """ + str(zoom) + """);

            // Add OpenStreetMap tile layer
            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);

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

            var marker = L.circleMarker(latlng, {
                radius: 5,
                fillColor: '#00FF00',
                fillOpacity: 0.8,
                color: '#FFFFFF',
                weight: 2
            }).addTo(drawnItems);

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

            var bounds = L.latLngBounds(polygonPoints);
            var latMin = bounds.getSouth();
            var latMax = bounds.getNorth();
            var lngMin = bounds.getWest();
            var lngMax = bounds.getEast();

            var latDiff = latMax - latMin;
            var lngDiff = lngMax - lngMin;
            var widthFt = Math.abs(latDiff) * 364000;
            var depthFt = Math.abs(lngDiff) * 364000 * 0.7071;

            updateInfo('Property: ' + widthFt.toFixed(0) + "' x " + depthFt.toFixed(0) + "' - Click Save & Return');

            window.boundaryData = {
                lat_min: latMin,
                lat_max: latMax,
                lng_min: lngMin,
                lng_max: lngMax,
                width_ft: widthFt,
                depth_ft: depthFt
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

        function saveAndReturn() {
            if (!hasBoundary || !window.boundaryData) {
                updateInfo('Please draw a boundary first!');
                return;
            }

            var b = window.boundaryData;

            // Send to server
            fetch('/boundary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(b)
            })
            .then(response => response.json())
            .then(data => {
                updateInfo('Boundary saved! You can close this tab.');
                document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;font-size:24px;"><h2 style="color:green;">✓ Boundary Saved!</h2><p>You can close this tab and return to the application.</p></div>';
            })
            .catch(error => {
                console.error('Error:', error);
                updateInfo('Error saving boundary!');
            });
        }

        function updateInfo(text) {
            document.getElementById('info').textContent = text;
        }

        window.onload = initMap;
    </script>
</body>
</html>"""


def start_server(output_file, lat, lng, zoom, port=8766):
    """Start HTTP server and open browser."""
    # Create a custom server class to store our data
    class MapServer(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lat = lat
            self.lng = lng
            self.zoom = zoom
            self.output_file = output_file
            self.allow_reuse_address = True  # Allow port reuse

    # Change to the widgets directory so it can serve files
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Try multiple ports if the default is in use
    max_port_attempts = 10
    server = None

    for attempt in range(max_port_attempts):
        try:
            current_port = port + attempt
            server = MapServer(('', current_port), MapHandler)
            server.timeout = None  # Run indefinitely
            print(f"[Map] Server started on port {current_port}")
            break
        except OSError as e:
            if e.winerror == 10048 or e.errno == 98:  # Port already in use (Windows/Linux)
                print(f"[Map] Port {current_port} in use, trying next...")
                continue
            else:
                raise

    if server is None:
        print(f"[Map] ERROR: Could not find available port after {max_port_attempts} attempts")
        return

    # Get actual port from server
    actual_port = server.server_address[1]

    # Open browser
    url = f'http://localhost:{actual_port}/map'
    print(f"[Map] Opening browser at {url}")
    webbrowser.open(url)

    print("[Map] Waiting for boundary data... (Close browser tab when done)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[Map] Server stopped")


def main():
    parser = argparse.ArgumentParser(description='OpenStreetMap Browser Launcher')
    parser.add_argument('--lat', type=float, default=45.4215, help='Center latitude')
    parser.add_argument('--lng', type=float, default=-75.6972, help='Center longitude')
    parser.add_argument('--zoom', type=int, default=16, help='Zoom level')
    parser.add_argument('--output', required=True, help='Output JSON file for boundary data')
    parser.add_argument('--port', type=int, default=8766, help='HTTP server port')

    args = parser.parse_args()

    print("[Map] Starting OpenStreetMap browser launcher")
    print("[Map] Location: (%.6f, %.6f), zoom %d" % (args.lat, args.lng, args.zoom))

    start_server(args.output, args.lat, args.lng, args.zoom, args.port)


if __name__ == '__main__':
    main()
