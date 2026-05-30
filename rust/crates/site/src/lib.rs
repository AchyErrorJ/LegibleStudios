//! Site / geospatial layer for Legible Studio.
//!
//! Native, dependency-light geo primitives: WGS84 ↔ UTM (Ontario zone 17N
//! today, with a path to other zones) and the slippy-map tile schema
//! (lat/lon ↔ tile XYZ at zoom Z). These two are the foundation the OSM
//! tile fetcher (increment 2), the native map widget (increment 3), and
//! the LiDAR backend (increments 4–6) build on.

pub mod coord;
pub mod geotiff;
pub mod ontario;
pub mod tile;
pub mod tilefetch;

pub use coord::{LatLon, UtmCoord, utm17_from_wgs84, wgs84_from_utm17};
pub use geotiff::{
    ElevationRaster, GeoAffine, GeoTiffError, GeoTiffInfo, read_elevation, read_info,
};
pub use ontario::{
    ClassifiedTiles, KNOWN_REGIONS, LocalTileIndex, OntarioTile, PACKAGE_BASE_URL,
    PackageResolver, StaticPackageResolver, TILE_SIDE_M, parse_tile_prefix, region_for,
    tiles_for_utm_bbox, tiles_for_wgs84_bbox,
};
pub use tile::{
    TILE_SIZE_PX, TileCoord, lat_lon_to_tile, lat_lon_to_tile_f64,
    lat_lon_to_world_pixel, tile_to_lat_lon, tile_to_pixel, world_pixel_to_lat_lon,
};
pub use tilefetch::{FetchError, TileFetcher, TileImage, decode_png_to_rgba};
