"""
Parametric Family Builder

Orchestrates the creation of parametric Revit families by calling
the C# family editor routes.

Workflow:
1. Create family document from template
2. Add family parameters (Width, Height, Depth, etc.)
3. Create reference planes for each dimension
4. Create solid extrusions from geometry definition
5. Create void extrusions for cutouts
6. Bind geometry to parameters via dimensions
7. Save family
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any, Optional


class ParametricFamilyBuilder:
    """
    Builds parametric Revit families from geometry definitions.
    """

    REVIT_API_URL = "http://localhost:48884/revit_mcp"

    # Category to template mapping
    CATEGORY_TEMPLATES = {
        "Furniture": "Metric Generic Model.rft",
        "Casework": "Metric Generic Model.rft",
        "Generic Models": "Metric Generic Model.rft",
        "Specialty Equipment": "Metric Generic Model.rft",
        "Plumbing Fixtures": "Metric Plumbing Fixture.rft",
        "Lighting Fixtures": "Metric Lighting Fixture.rft",
        "Electrical Fixtures": "Metric Electrical Fixture.rft",
    }

    # Retry settings for document switching
    MAX_VERIFY_RETRIES = 5
    VERIFY_RETRY_DELAY = 1.0  # seconds

    def __init__(self, revit_url: Optional[str] = None):
        """Initialize builder with Revit API URL"""
        self.revit_url = revit_url or self.REVIT_API_URL
        self.created_elements = {}  # Track created element IDs
        self.family_name = None  # Track expected family name

    async def _post(self, endpoint: str, payload: Dict) -> Dict:
        """Send POST request to Revit API"""
        url = f"{self.revit_url}{endpoint}"
        if not url.endswith("/"):
            url += "/"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=60.0)
                return response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def _get(self, endpoint: str) -> Dict:
        """Send GET request to Revit API"""
        url = f"{self.revit_url}{endpoint}"
        if not url.endswith("/"):
            url += "/"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30.0)
                return response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def verify_family_document(self) -> Dict:
        """
        Verify that the active document is a family document.
        Returns status with details about the current document.
        """
        result = await self._post("/family/verify", {})
        return result

    async def get_document_status(self) -> Dict:
        """Get current document status"""
        result = await self._post("/family/document_status", {})
        return result

    async def wait_for_family_document(self, expected_name: str = None, max_retries: int = None) -> Dict:
        """
        Wait for the active document to be a family document.
        Useful after creating a new family when Revit needs time to switch.

        Args:
            expected_name: Optional expected family name to match
            max_retries: Maximum number of retries (default: MAX_VERIFY_RETRIES)

        Returns:
            Verification result or error after retries exhausted
        """
        import asyncio

        retries = max_retries or self.MAX_VERIFY_RETRIES

        for attempt in range(retries):
            result = await self.verify_family_document()

            if result.get("status") == "success" and result.get("is_family_document"):
                # If we have an expected name, check it
                if expected_name:
                    doc_title = result.get("document_title", "")
                    # Family titles often include "Family1" suffix, so check if it starts with expected
                    if expected_name.lower() in doc_title.lower():
                        print(f"   ✅ Family document verified: {doc_title}")
                        return result
                    else:
                        print(f"   ⚠️ Wrong family active: {doc_title} (expected: {expected_name})")
                else:
                    print(f"   ✅ Family document active: {result.get('document_title')}")
                    return result

            print(f"   ⏳ Waiting for family document... (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(self.VERIFY_RETRY_DELAY)

        # Final check
        final_result = await self.get_document_status()
        return {
            "status": "error",
            "message": "Timeout waiting for family document to become active",
            "hint": "Please manually switch to the family document in Revit and try again",
            "current_document": final_result.get("document_title"),
            "is_family": final_result.get("is_family_document", False)
        }

    async def build_family(
        self,
        geometry_def: Dict,
        family_name: str,
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - builds complete parametric family.

        Args:
            geometry_def: Geometry definition from PhotoToFamilyProcessor
            family_name: Name for the new family
            save_path: Optional path to save .rfa file

        Returns:
            Result with status and created element IDs
        """
        print(f"\n   Building parametric family: {family_name}")
        self.created_elements = {}
        self.family_name = family_name
        results = []

        try:
            # 1. Create family document
            category = geometry_def.get("category", "Generic Models")
            template = self.CATEGORY_TEMPLATES.get(category, "Metric Generic Model.rft")
            doc_result = await self.create_family_document(template, family_name, category)
            results.append(("create_document", doc_result))

            if doc_result.get("status") != "success":
                return {"status": "error", "message": f"Failed to create family: {doc_result.get('message')}", "results": results}

            # 1b. SAFETY CHECK - Wait for family document to be active
            print(f"   Verifying family document is active...")
            verify_result = await self.wait_for_family_document(expected_name=family_name)
            results.append(("verify_document", verify_result))

            if verify_result.get("status") != "success":
                return {
                    "status": "error",
                    "message": "Family document not active after creation",
                    "hint": verify_result.get("hint", "Please switch to the family document in Revit"),
                    "current_document": verify_result.get("current_document"),
                    "results": results
                }

            # 2. Create parameters
            parameters = geometry_def.get("parameters", [])
            param_result = await self.add_parameters(parameters)
            results.append(("add_parameters", param_result))

            # 3. Create reference planes
            ref_planes_result = await self.create_reference_planes(parameters)
            results.append(("create_ref_planes", ref_planes_result))

            # 4. Create solids
            solids = geometry_def.get("solids", [])
            solids_result = await self.create_solids(solids)
            results.append(("create_solids", solids_result))

            # 5. Create voids
            voids = geometry_def.get("voids", [])
            if voids:
                voids_result = await self.create_voids(voids)
                results.append(("create_voids", voids_result))

            # 6. Bind parameters to geometry (create dimensions)
            binding_result = await self.bind_parameters_to_geometry(parameters)
            results.append(("bind_parameters", binding_result))

            print(f"   Family '{family_name}' created successfully!")

            return {
                "status": "success",
                "message": f"Created parametric family: {family_name}",
                "family_name": family_name,
                "category": category,
                "elements": self.created_elements,
                "results": results
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Family build failed: {str(e)}",
                "results": results
            }

    async def create_family_document(
        self,
        template: str,
        name: str,
        category: str
    ) -> Dict:
        """Create new family from template"""
        print(f"   Creating family document from {template}...")

        result = await self._post("/family/create_new", {
            "template_name": template,
            "family_name": name,
            "category_name": category
        })

        # DEBUG: Show full response
        print(f"   📋 create_new result: {result}")

        # Check if we need to explicitly open the family
        if result.get("status") == "success":
            family_path = result.get("path")
            is_active = result.get("is_active", False)

            # Always open if not active or if path exists and is_family_document is unclear
            if family_path and not is_active:
                print(f"   📂 Opening family file: {family_path}")
                open_result = await self._post("/family/open", {"path": family_path})
                print(f"   📋 open result: {open_result}")
                if open_result.get("status") == "success":
                    result["is_family_document"] = open_result.get("is_family_document", True)
                    result["opened_separately"] = True
                    print(f"   ✅ Family opened: {open_result.get('title')}")
                else:
                    print(f"   ⚠️ Failed to open family: {open_result.get('message')}")
                    result["open_error"] = open_result.get("message")

        return result

    async def add_parameters(self, params: List[Dict]) -> Dict:
        """Add all family parameters"""
        print(f"   Adding {len(params)} parameters...")
        results = []

        for param in params:
            result = await self._post("/family/create_parameter", {
                "param_name": param.get("name"),
                "param_type": param.get("type", "Length"),
                "group": "Dimensions",
                "is_instance": False
            })
            results.append(result)

            # Set initial value if provided
            if param.get("value") is not None and result.get("status") == "success":
                value_result = await self._post("/family/set_parameter_value", {
                    "param_name": param.get("name"),
                    "value": param.get("value")
                })
                results.append(value_result)

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count > 0 else "error",
            "created": success_count,
            "total": len(params),
            "details": results
        }

    async def create_reference_planes(self, params: List[Dict]) -> Dict:
        """Create reference planes for each dimension parameter"""
        print(f"   Creating reference planes...")
        results = []
        ref_plane_ids = {}

        # Standard reference planes for dimensions
        dimension_planes = {
            "Width": [
                {"name": "Left", "start": [0, 0, 0], "end": [0, 10, 0]},
                {"name": "Right", "start": [1, 0, 0], "end": [1, 10, 0]}
            ],
            "Height": [
                {"name": "Bottom", "start": [0, 0, 0], "end": [10, 0, 0]},
                {"name": "Top", "start": [0, 1, 0], "end": [10, 1, 0]}
            ],
            "Depth": [
                {"name": "Front", "start": [0, 0, 0], "end": [0, 10, 0]},
                {"name": "Back", "start": [0, 0, 1], "end": [0, 10, 1]}
            ]
        }

        for param in params:
            param_name = param.get("name")
            if param_name in dimension_planes:
                value = param.get("value", 1.0)
                planes = dimension_planes[param_name]

                for plane_def in planes:
                    # Scale points by parameter value
                    start = plane_def["start"].copy()
                    end = plane_def["end"].copy()

                    result = await self._post("/family/create_ref_plane", {
                        "start_point": start,
                        "end_point": end,
                        "name": f"{param_name}_{plane_def['name']}"
                    })
                    results.append(result)

                    if result.get("status") == "success":
                        ref_plane_ids[f"{param_name}_{plane_def['name']}"] = result.get("elementId")

        self.created_elements["reference_planes"] = ref_plane_ids

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count > 0 else "error",
            "created": success_count,
            "ref_plane_ids": ref_plane_ids,
            "details": results
        }

    async def create_solids(self, solids: List[Dict]) -> Dict:
        """Create all solid extrusions"""
        print(f"   Creating {len(solids)} solid(s)...")
        results = []
        solid_ids = {}

        for solid in solids:
            solid_type = solid.get("type", "extrusion")

            if solid_type == "extrusion":
                # Convert 2D profile to 3D points
                profile = solid.get("profile", [])
                offset = solid.get("offset", [0, 0, 0])
                height = solid.get("depth", 1.0)

                # Create 3D points at the offset elevation
                points_3d = []
                for point in profile:
                    x = point[0] + offset[0]
                    y = point[1] + offset[1]
                    z = offset[2] if len(offset) > 2 else 0
                    points_3d.append([x, y, z])

                result = await self._post("/family/create_extrusion", {
                    "points": points_3d,
                    "height": height,
                    "base_offset": 0
                })
                results.append(result)

                if result.get("status") == "success":
                    solid_ids[solid.get("name", f"solid_{len(solid_ids)}")] = result.get("elementId")

            elif solid_type == "blend":
                result = await self._post("/family/create_blend", {
                    "bottom_profile": solid.get("bottom_profile", solid.get("profile", [])),
                    "top_profile": solid.get("top_profile", []),
                    "top_offset": solid.get("depth", 1.0),
                    "is_solid": True
                })
                results.append(result)

                if result.get("status") == "success":
                    solid_ids[solid.get("name", f"blend_{len(solid_ids)}")] = result.get("elementId")

        self.created_elements["solids"] = solid_ids

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count > 0 else "error",
            "created": success_count,
            "total": len(solids),
            "solid_ids": solid_ids,
            "details": results
        }

    async def create_voids(self, voids: List[Dict]) -> Dict:
        """Create void extrusions and cut operations"""
        print(f"   Creating {len(voids)} void(s)...")
        results = []
        void_ids = {}

        for void in voids:
            # Create void extrusion
            profile = void.get("profile", [])
            offset = void.get("offset", [0, 0, 0])
            height = void.get("depth", 1.0)

            points_3d = []
            for point in profile:
                x = point[0] + offset[0]
                y = point[1] + offset[1]
                z = offset[2] if len(offset) > 2 else 0
                points_3d.append([x, y, z])

            result = await self._post("/family/create_void", {
                "points": points_3d,
                "height": height,
                "base_offset": 0
            })
            results.append(result)

            if result.get("status") == "success":
                void_id = result.get("elementId")
                void_ids[void.get("name", f"void_{len(void_ids)}")] = void_id

                # Apply cut if target solid specified
                cut_from = void.get("cut_from")
                if cut_from and cut_from in self.created_elements.get("solids", {}):
                    solid_id = self.created_elements["solids"][cut_from]
                    cut_result = await self._post("/family/cut_solid", {
                        "solid_id": int(solid_id),
                        "void_id": int(void_id)
                    })
                    results.append(cut_result)

        self.created_elements["voids"] = void_ids

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count > 0 else "partial" if success_count > 0 else "error",
            "created": success_count,
            "total": len(voids),
            "void_ids": void_ids,
            "details": results
        }

    async def bind_parameters_to_geometry(self, params: List[Dict]) -> Dict:
        """Create dimensional constraints linking geometry to parameters"""
        print(f"   Binding parameters to geometry...")
        results = []

        # Create dimensions between reference planes and bind to parameters
        ref_planes = self.created_elements.get("reference_planes", {})

        for param in params:
            param_name = param.get("name")

            # Find corresponding reference plane pairs
            plane1_name = f"{param_name}_Left" if param_name == "Width" else f"{param_name}_Bottom" if param_name == "Height" else f"{param_name}_Front"
            plane2_name = f"{param_name}_Right" if param_name == "Width" else f"{param_name}_Top" if param_name == "Height" else f"{param_name}_Back"

            if plane1_name in ref_planes and plane2_name in ref_planes:
                result = await self._post("/family/create_dimension", {
                    "ref_plane_1": plane1_name,
                    "ref_plane_2": plane2_name,
                    "param_name": param_name
                })
                results.append(result)

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count > 0 else "partial",
            "bound": success_count,
            "total": len(params),
            "details": results
        }

    async def ensure_family_context(self) -> bool:
        """
        Quick check to ensure we're still in a family document context.
        Returns True if ok, raises exception if not.
        """
        result = await self.verify_family_document()
        if result.get("status") != "success" or not result.get("is_family_document"):
            raise RuntimeError(
                f"Lost family document context. Current document: {result.get('document_title', 'unknown')}. "
                f"Please switch back to the family document in Revit."
            )
        return True

    async def save_family(self, path: str = None) -> Dict:
        """Save family to disk"""
        # First verify we're in a family document
        verify = await self.verify_family_document()
        if verify.get("status") != "success" or not verify.get("is_family_document"):
            return {
                "status": "error",
                "message": "Cannot save - not in a family document",
                "current_document": verify.get("document_title")
            }

        result = await self._post("/family/save", {
            "path": path,
            "overwrite": True
        })
        return result


# Simple test
async def test_builder():
    """Test the family builder with a simple geometry"""
    builder = ParametricFamilyBuilder()

    # Simple box geometry
    geometry = {
        "object_type": "table",
        "category": "Furniture",
        "parameters": [
            {"name": "Width", "value": 4.0, "type": "Length"},
            {"name": "Height", "value": 2.5, "type": "Length"},
            {"name": "Depth", "value": 2.0, "type": "Length"}
        ],
        "solids": [
            {
                "name": "tabletop",
                "type": "extrusion",
                "profile": [[0, 0], [4, 0], [4, 0.1], [0, 0.1]],
                "depth": 2.0,
                "offset": [0, 2.4, 0]
            }
        ],
        "voids": []
    }

    result = await builder.build_family(geometry, "Test_Table")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(test_builder())
