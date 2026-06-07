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

    def __init__(self, output_file, api_key=None):
        self.output_file = output_file
        self.boundary_data = None
        self.building_origin = None
        self.api_key = api_key  # Google Maps API key for elevation

    def probe_elevation(self, lat, lng):
        """Fetch elevation at a single point using Google Maps API."""
        if not self.api_key:
            return {"error": "No API key configured. Enter your Google Maps API key in Site Dialog."}

        try:
            url = "https://maps.googleapis.com/maps/api/elevation/json"
            params = {
                "locations": f"{lat},{lng}",
                "key": self.api_key
            }
            print(f"[Map] Probing elevation at ({lat:.6f}, {lng:.6f})")
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and data.get("results"):
                    elev_m = data["results"][0]["elevation"]
                    elev_ft = elev_m * 3.28084
                    resolution = data["results"][0].get("resolution", 0)
                    print(f"[Map] Elevation: {elev_m:.2f}m ({elev_ft:.2f}ft), resolution: {resolution:.1f}m")
                    return {
                        "elevation_m": round(elev_m, 2),
                        "elevation_ft": round(elev_ft, 2),
                        "resolution_m": round(resolution, 1),
                        "lat": lat,
                        "lng": lng
                    }
                else:
                    error = data.get("error_message", data.get("status", "Unknown error"))
                    print(f"[Map] Elevation API error: {error}")
                    return {"error": error}
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            print(f"[Map] Elevation probe error: {e}")
            return {"error": str(e)}

    def set_boundary(self, lat_min, lat_max, lng_min, lng_max, width_ft, depth_ft, vertices_json=None, vertices_ft_json=None):
        """Called from JavaScript when boundary is drawn."""
        print("[Map] set_boundary called: %.0f' x %.0f'" % (width_ft, depth_ft))

        # Parse polygon vertices if provided
        vertices = None
        vertices_ft = None
        if vertices_json:
            try:
                vertices = json.loads(vertices_json)
                print("[Map] Polygon has %d vertices" % len(vertices))
            except:
                pass
        if vertices_ft_json:
            try:
                vertices_ft = json.loads(vertices_ft_json)
            except:
                pass

        self.boundary_data = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lng_min': lng_min,
            'lng_max': lng_max,
            'width_ft': width_ft,
            'depth_ft': depth_ft,
            'vertices': vertices,        # [[lat, lng], ...] - actual polygon shape
            'vertices_ft': vertices_ft   # [[x_ft, z_ft], ...] - in local coordinates
        }
        self._save_data()

    def set_building_origin(self, lat, lng, x_ft, z_ft, rotation_deg):
        """Called from JavaScript when building placement is set."""
        print("[Map] set_building_origin called: (%.6f, %.6f) -> (%.1f', %.1f') rotation=%.1f°" % (lat, lng, x_ft, z_ft, rotation_deg))
        self.building_origin = {
            'lat': lat,
            'lng': lng,
            'x_ft': x_ft,  # Center X from west edge of property in feet
            'z_ft': z_ft,  # Center Z from south edge of property in feet
            'rotation_deg': rotation_deg  # Rotation in degrees (0 = north-aligned)
        }
        self._save_data()

    def _save_data(self):
        """Save boundary and building origin to file."""
        try:
            data = {}
            if self.boundary_data:
                data['boundary'] = self.boundary_data
            if self.building_origin:
                data['building_origin'] = self.building_origin
            with open(self.output_file, 'w') as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            print("[Map] Data saved to %s" % self.output_file)
        except Exception as e:
            print("[Map] Error saving data: %s" % e)
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
            max-width: 350px;
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
        .controls button.building { background: #2196F3; }
        .controls button.building:hover { background: #1976D2; }
        .controls button:disabled { background: #ccc; cursor: not-allowed; }
        .section { margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 4px; }
        .section-title { font-weight: bold; font-size: 13px; margin-bottom: 8px; color: #333; }
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
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 5px;
        }
        .status-pending { background: #FFC107; color: #333; }
        .status-done { background: #4CAF50; color: white; }
    </style>
</head>
<body>
    <div class="controls">
        <h3>Site & Building Placement</h3>

        <div class="section">
            <div class="section-title">Step 1: Draw Property Boundary <span id="boundaryStatus" class="status-badge status-pending">pending</span></div>
            <p style="font-size: 11px; margin: 5px 0;">Click points around your property line</p>
            <button onclick="startDrawing()">Start Drawing</button>
            <button onclick="finishPolygon()" class="secondary">Finish</button>
            <button onclick="clearBoundary()" class="secondary">Clear</button>
        </div>

        <div class="section">
            <div class="section-title">Step 2: Place Building <span id="buildingStatus" class="status-badge status-pending">pending</span></div>
            <p style="font-size: 11px; margin: 5px 0;">Click inside boundary to set building center</p>
            <button id="placeBuildingBtn" onclick="startPlaceBuilding()" class="building" disabled>Place Building</button>
            <button onclick="clearBuilding()" class="secondary">Clear</button>
            <div id="rotationControl" style="display: none; margin-top: 10px;">
                <label style="font-size: 12px;">Rotation: <span id="rotationValue">0</span>°</label>
                <input type="range" id="rotationSlider" min="0" max="360" value="0" style="width: 100%%;" oninput="onRotationChange(this.value)">
            </div>
        </div>

        <div class="section" style="background: #fff3cd;">
            <div class="section-title">🔍 Elevation Probe (Testing)</div>
            <p style="font-size: 11px; margin: 5px 0;">Click anywhere to test elevation reading</p>
            <button id="probeBtn" onclick="toggleProbeMode()" style="background: #FF9800;">Start Probe</button>
            <div id="probeResults" style="margin-top: 8px; font-size: 11px; color: #333; display: none;">
                <div id="probeData">Click on map...</div>
            </div>
        </div>

        <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
        <button onclick="saveAndClose()" class="success" style="width: calc(100%% - 10px);">Save & Close</button>
    </div>
    <div id="map"></div>
    <div class="info" id="info">Loading map...</div>

    <script>
        var map;
        var drawnItems;
        var buildingLayer;
        var polygonPoints = [];
        var polygon = null;
        var hasBoundary = false;
        var buildingMarker = null;
        var buildingFootprint = null;
        var hasBuilding = false;
        var isPlacingBuilding = false;
        var buildingRotation = 0;  // Degrees
        var buildingLatLng = null;
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

            // Initialize layers
            drawnItems = L.featureGroup().addTo(map);
            buildingLayer = L.featureGroup().addTo(map);

            updateInfo('Map loaded! Step 1: Draw property boundary');
        }

        function startDrawing() {
            if (polygon) {
                clearBoundary();
            }
            isPlacingBuilding = false;
            updateInfo('Click on map to place boundary points. Click Finish when done.');
            map.on('click', onBoundaryClick);
            map.doubleClickZoom.disable();
        }

        function onBoundaryClick(e) {
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

            map.off('click', onBoundaryClick);
            map.doubleClickZoom.enable();

            hasBoundary = true;

            // Get bounds
            var bounds = L.latLngBounds(polygonPoints);
            var latMin = bounds.getSouth();
            var latMax = bounds.getNorth();
            var lngMin = bounds.getWest();
            var lngMax = bounds.getEast();

            // Calculate approximate dimensions (lat = north-south = depth, lng = east-west = width)
            var latDiff = latMax - latMin;
            var lngDiff = lngMax - lngMin;
            // 1 degree lat ~ 364,000 ft, 1 degree lng ~ 364,000 * cos(lat) ft
            var centerLat = (latMin + latMax) / 2;
            var depthFt = Math.abs(latDiff) * 364000;
            var widthFt = Math.abs(lngDiff) * 364000 * Math.cos(centerLat * Math.PI / 180);
            var area = widthFt * depthFt;

            // Update status
            document.getElementById('boundaryStatus').className = 'status-badge status-done';
            document.getElementById('boundaryStatus').textContent = 'done';
            document.getElementById('placeBuildingBtn').disabled = false;

            updateInfo('Property: ' + widthFt.toFixed(0) + "' x " + depthFt.toFixed(0) + "' - Now place your building!");

            // Convert polygon points to array of [lat, lng] for storage
            var vertices = polygonPoints.map(function(p) {
                return [p.lat, p.lng];
            });

            // Also convert to local coordinates (feet from SW corner)
            var verticesFt = polygonPoints.map(function(p) {
                var xFt = (p.lng - lngMin) * 364000 * Math.cos(centerLat * Math.PI / 180);
                var zFt = (p.lat - latMin) * 364000;
                return [xFt, zFt];
            });

            // Store boundary data with actual polygon vertices
            window.boundaryData = {
                latMin: latMin,
                latMax: latMax,
                lngMin: lngMin,
                lngMax: lngMax,
                widthFt: widthFt,
                depthFt: depthFt,
                centerLat: centerLat,
                vertices: vertices,        // Actual polygon in lat/lng
                verticesFt: verticesFt     // Polygon in local feet coordinates
            };

            // Send boundary to Python (including vertices)
            if (pywebview && pywebview.api && pywebview.api.set_boundary) {
                pywebview.api.set_boundary(latMin, latMax, lngMin, lngMax, widthFt, depthFt, JSON.stringify(vertices), JSON.stringify(verticesFt));
            }
        }

        function clearBoundary() {
            drawnItems.clearLayers();
            polygon = null;
            polygonPoints = [];
            hasBoundary = false;
            window.boundaryData = null;
            map.off('click', onBoundaryClick);
            map.doubleClickZoom.enable();

            // Reset status
            document.getElementById('boundaryStatus').className = 'status-badge status-pending';
            document.getElementById('boundaryStatus').textContent = 'pending';
            document.getElementById('placeBuildingBtn').disabled = true;

            // Also clear building
            clearBuilding();

            updateInfo('Boundary cleared. Click Start Drawing to begin.');
        }

        function startPlaceBuilding() {
            if (!hasBoundary) {
                updateInfo('Please draw a property boundary first!');
                return;
            }

            isPlacingBuilding = true;
            map.off('click', onBoundaryClick);
            map.on('click', onBuildingClick);
            updateInfo('Click inside your property to place the building origin (southwest corner)');
        }

        function onBuildingClick(e) {
            if (!isPlacingBuilding || !window.boundaryData) return;

            var latlng = e.latlng;
            var b = window.boundaryData;

            // Check if click is inside boundary (rough check using bounds)
            if (latlng.lat < b.latMin || latlng.lat > b.latMax ||
                latlng.lng < b.lngMin || latlng.lng > b.lngMax) {
                updateInfo('Please click INSIDE the property boundary!');
                return;
            }

            // Clear previous building
            buildingLayer.clearLayers();

            // Store building position
            buildingLatLng = latlng;
            buildingRotation = 0;

            // Create building visualization
            createBuildingVisualization();

            hasBuilding = true;
            isPlacingBuilding = false;
            map.off('click', onBuildingClick);

            // Show rotation control
            document.getElementById('rotationControl').style.display = 'block';
            document.getElementById('rotationSlider').value = 0;
            document.getElementById('rotationValue').textContent = '0';

            // Update status
            document.getElementById('buildingStatus').className = 'status-badge status-done';
            document.getElementById('buildingStatus').textContent = 'done';

            // Send to Python
            sendBuildingData();
        }

        function createBuildingVisualization() {
            if (!buildingLatLng || !window.boundaryData) return;

            buildingLayer.clearLayers();

            // Add center marker (draggable)
            buildingMarker = L.marker(buildingLatLng, {
                icon: L.divIcon({
                    className: 'building-icon',
                    html: '<div style="width:16px;height:16px;background:#2196F3;border:3px solid white;border-radius:50%%;box-shadow:0 2px 6px rgba(0,0,0,0.5);"></div>',
                    iconSize: [22, 22],
                    iconAnchor: [11, 11]
                }),
                draggable: true
            }).addTo(buildingLayer);

            // Create rotated rectangle footprint (represents building outline)
            // Size based on a typical house footprint scaled to map
            var b = window.boundaryData;
            var latScale = (b.latMax - b.latMin) / b.depthFt;
            var lngScale = (b.lngMax - b.lngMin) / b.widthFt;

            // Footprint size: ~40' x 30' typical house
            var halfWidth = 20 * lngScale;  // 20ft from center
            var halfDepth = 15 * latScale;  // 15ft from center

            var footprintPoints = getRotatedRectangle(buildingLatLng, halfWidth, halfDepth, buildingRotation);
            buildingFootprint = L.polygon(footprintPoints, {
                color: '#2196F3',
                fillColor: '#2196F3',
                fillOpacity: 0.3,
                weight: 2
            }).addTo(buildingLayer);

            // Add direction indicator (shows "front" of building)
            var frontPoint = rotatePoint(buildingLatLng, 0, halfDepth * 1.5, buildingRotation);
            L.polyline([buildingLatLng, frontPoint], {
                color: '#FF5722',
                weight: 3,
                dashArray: '5, 5'
            }).addTo(buildingLayer);

            // Handle marker drag
            buildingMarker.on('drag', function(e) {
                buildingLatLng = e.target.getLatLng();
                createBuildingVisualization();
            });

            buildingMarker.on('dragend', function(e) {
                buildingLatLng = e.target.getLatLng();
                createBuildingVisualization();
                sendBuildingData();
            });

            updateBuildingInfo();
        }

        function getRotatedRectangle(center, halfWidth, halfDepth, angleDeg) {
            // Get 4 corners of rectangle rotated around center
            var corners = [
                [-halfWidth, -halfDepth],
                [halfWidth, -halfDepth],
                [halfWidth, halfDepth],
                [-halfWidth, halfDepth]
            ];

            return corners.map(function(c) {
                return rotatePoint(center, c[0], c[1], angleDeg);
            });
        }

        function rotatePoint(center, dx, dy, angleDeg) {
            var angleRad = angleDeg * Math.PI / 180;
            var cosA = Math.cos(angleRad);
            var sinA = Math.sin(angleRad);
            var rotX = dx * cosA - dy * sinA;
            var rotY = dx * sinA + dy * cosA;
            return L.latLng(center.lat + rotY, center.lng + rotX);
        }

        function onRotationChange(value) {
            buildingRotation = parseInt(value);
            document.getElementById('rotationValue').textContent = value;
            if (hasBuilding && buildingLatLng) {
                createBuildingVisualization();
                sendBuildingData();
            }
        }

        function updateBuildingInfo() {
            if (!buildingLatLng || !window.boundaryData) return;

            var b = window.boundaryData;
            var xFraction = (buildingLatLng.lng - b.lngMin) / (b.lngMax - b.lngMin);
            var zFraction = (buildingLatLng.lat - b.latMin) / (b.latMax - b.latMin);
            var xFt = xFraction * b.widthFt;
            var zFt = zFraction * b.depthFt;

            updateInfo('Building center: (' + xFt.toFixed(0) + "', " + zFt.toFixed(0) + "') | Rotation: " + buildingRotation + "°");
        }

        function sendBuildingData() {
            if (!buildingLatLng || !window.boundaryData) return;

            var b = window.boundaryData;
            var xFraction = (buildingLatLng.lng - b.lngMin) / (b.lngMax - b.lngMin);
            var zFraction = (buildingLatLng.lat - b.latMin) / (b.latMax - b.latMin);
            var xFt = xFraction * b.widthFt;
            var zFt = zFraction * b.depthFt;

            window.buildingOrigin = {
                lat: buildingLatLng.lat,
                lng: buildingLatLng.lng,
                xFt: xFt,
                zFt: zFt,
                rotationDeg: buildingRotation
            };

            if (pywebview && pywebview.api && pywebview.api.set_building_origin) {
                pywebview.api.set_building_origin(buildingLatLng.lat, buildingLatLng.lng, xFt, zFt, buildingRotation);
            }

            updateBuildingInfo();
        }

        function clearBuilding() {
            buildingLayer.clearLayers();
            buildingMarker = null;
            buildingFootprint = null;
            buildingLatLng = null;
            buildingRotation = 0;
            hasBuilding = false;
            isPlacingBuilding = false;
            window.buildingOrigin = null;
            map.off('click', onBuildingClick);

            // Hide rotation control
            document.getElementById('rotationControl').style.display = 'none';

            document.getElementById('buildingStatus').className = 'status-badge status-pending';
            document.getElementById('buildingStatus').textContent = 'pending';

            if (hasBoundary) {
                updateInfo('Building cleared. Click Place Building to set a new location.');
            }
        }

        function saveAndClose() {
            if (!hasBoundary || !window.boundaryData) {
                updateInfo('Please draw a boundary first!');
                return;
            }

            if (!hasBuilding || !window.buildingOrigin) {
                // Allow saving without building placement - it will default to origin
                if (!confirm('No building placement set. Building will be placed at property origin (0,0). Continue?')) {
                    return;
                }
                // Set default building origin at property origin (0,0)
                var b = window.boundaryData;
                if (b && pywebview && pywebview.api && pywebview.api.set_building_origin) {
                    // Default to center of property (width/2, depth/2) with no rotation
                    var defaultX = b.widthFt / 2;
                    var defaultZ = b.depthFt / 2;
                    // Calculate lat/lng for center
                    var centerLat = (b.latMin + b.latMax) / 2;
                    var centerLng = (b.lngMin + b.lngMax) / 2;
                    console.log('[Map] Setting default building origin at center: (' + defaultX + ', ' + defaultZ + ')');
                    pywebview.api.set_building_origin(centerLat, centerLng, defaultX, defaultZ, 0);
                }
            }

            updateInfo('Saving... closing window');

            setTimeout(function() {
                if (pywebview && pywebview.api && pywebview.api.save_and_close) {
                    pywebview.api.save_and_close();
                } else {
                    window.close();
                }
            }, 300);
        }

        function updateInfo(text) {
            document.getElementById('info').textContent = text;
        }

        // ============ ELEVATION PROBE ============
        var isProbing = false;
        var probeMarker = null;
        var probeHistory = [];  // Store probe points for comparison

        function toggleProbeMode() {
            isProbing = !isProbing;
            var btn = document.getElementById('probeBtn');
            var results = document.getElementById('probeResults');

            if (isProbing) {
                btn.textContent = 'Stop Probe';
                btn.style.background = '#f44336';
                results.style.display = 'block';
                document.getElementById('probeData').innerHTML = 'Click on map to probe elevation...';

                // Disable other click handlers temporarily
                map.off('click', onBoundaryClick);
                map.off('click', onBuildingClick);
                map.on('click', onProbeClick);

                updateInfo('PROBE MODE: Click anywhere to check elevation');
            } else {
                btn.textContent = 'Start Probe';
                btn.style.background = '#FF9800';
                map.off('click', onProbeClick);

                // Clear probe marker
                if (probeMarker) {
                    map.removeLayer(probeMarker);
                    probeMarker = null;
                }

                updateInfo('Probe mode disabled');
            }
        }

        function onProbeClick(e) {
            var latlng = e.latlng;
            document.getElementById('probeData').innerHTML =
                '<b>Lat:</b> ' + latlng.lat.toFixed(6) + '<br>' +
                '<b>Lng:</b> ' + latlng.lng.toFixed(6) + '<br>' +
                '<i>Fetching elevation...</i>';

            // Add/move marker
            if (probeMarker) {
                probeMarker.setLatLng(latlng);
            } else {
                probeMarker = L.marker(latlng, {
                    icon: L.divIcon({
                        className: 'probe-icon',
                        html: '<div style="width:20px;height:20px;background:#FF9800;border:3px solid white;border-radius:50%%;display:flex;align-items:center;justify-content:center;font-size:12px;color:white;font-weight:bold;">?</div>',
                        iconSize: [26, 26],
                        iconAnchor: [13, 13]
                    })
                }).addTo(map);
            }

            // Call Python API to fetch elevation
            if (pywebview && pywebview.api && pywebview.api.probe_elevation) {
                pywebview.api.probe_elevation(latlng.lat, latlng.lng).then(function(result) {
                    if (result.error) {
                        document.getElementById('probeData').innerHTML =
                            '<b>Lat:</b> ' + latlng.lat.toFixed(6) + '<br>' +
                            '<b>Lng:</b> ' + latlng.lng.toFixed(6) + '<br>' +
                            '<span style="color:red;"><b>Error:</b> ' + result.error + '</span>';
                    } else {
                        // Store in history
                        probeHistory.push({
                            lat: result.lat,
                            lng: result.lng,
                            elev_ft: result.elevation_ft,
                            elev_m: result.elevation_m
                        });

                        // Calculate min/max from history
                        var minElev = Math.min(...probeHistory.map(p => p.elev_ft));
                        var maxElev = Math.max(...probeHistory.map(p => p.elev_ft));
                        var elevRange = maxElev - minElev;

                        var historyInfo = '';
                        if (probeHistory.length > 1) {
                            historyInfo = '<br><b>Session:</b> ' + probeHistory.length + ' probes, range: ' + elevRange.toFixed(1) + ' ft (' + minElev.toFixed(1) + ' to ' + maxElev.toFixed(1) + ' ft)';
                        }

                        document.getElementById('probeData').innerHTML =
                            '<b>Lat:</b> ' + latlng.lat.toFixed(6) + '<br>' +
                            '<b>Lng:</b> ' + latlng.lng.toFixed(6) + '<br>' +
                            '<b style="color:#4CAF50;">Elevation:</b> <span style="font-size:14px;font-weight:bold;">' + result.elevation_ft.toFixed(1) + ' ft</span> (' + result.elevation_m.toFixed(1) + 'm)<br>' +
                            '<b>Resolution:</b> ' + result.resolution_m + 'm' +
                            historyInfo;

                        // Update marker to show elevation
                        if (probeMarker) {
                            probeMarker.setIcon(L.divIcon({
                                className: 'probe-icon',
                                html: '<div style="min-width:40px;height:20px;background:#4CAF50;border:2px solid white;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:11px;color:white;font-weight:bold;padding:0 6px;">' + result.elevation_ft.toFixed(0) + ' ft</div>',
                                iconSize: [50, 24],
                                iconAnchor: [25, 12]
                            }));
                        }

                        updateInfo('Elevation: ' + result.elevation_ft.toFixed(1) + ' ft (' + result.elevation_m.toFixed(1) + 'm) - Click again to compare');
                    }
                });
            } else {
                document.getElementById('probeData').innerHTML =
                    '<b>Lat:</b> ' + latlng.lat.toFixed(6) + '<br>' +
                    '<b>Lng:</b> ' + latlng.lng.toFixed(6) + '<br>' +
                    '<span style="color:orange;"><b>Note:</b> No API key. Enter key in Site Dialog to enable elevation probing.</span>';
            }
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
    parser.add_argument('--api-key', help='Google Maps API key for elevation probing')
    parser.add_argument('--lat', type=float, default=45.4215, help='Center latitude')
    parser.add_argument('--lng', type=float, default=-75.6972, help='Center longitude')
    parser.add_argument('--zoom', type=int, default=16, help='Zoom level')
    parser.add_argument('--output', required=True, help='Output JSON file for boundary data')

    args = parser.parse_args()

    print("[Map] Starting OpenStreetMap at (%f, %f), zoom %d" % (args.lat, args.lng, args.zoom))
    if args.api_key:
        print("[Map] Elevation probe enabled with API key")

    api = MapAPI(args.output, api_key=args.api_key)
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

    webview.start(debug=True)  # Enable dev tools - right click to inspect


if __name__ == '__main__':
    main()
