//! Site / geospatial layer for Legible Studio.
//!
//! Native, dependency-light geo primitives: WGS84 ↔ UTM (Ontario zone 17N
//! today, with a path to other zones) and the slippy-map tile schema
//! (lat/lon ↔ tile XYZ at zoom Z). These two are the foundation the OSM
//! tile fetcher (increment 2), the native map widget (increment 3), and
//! the LiDAR backend (increments 4–6) build on.

pub mod coord;
pub mod tile;
pub mod tilefetch;

pub use coord::{LatLon, UtmCoord, utm17_from_wgs84, wgs84_from_utm17};
pub use tile::{TileCoord, lat_lon_to_tile, tile_to_lat_lon, tile_to_pixel};
pub use tilefetch::{FetchError, TileFetcher, TileImage, decode_png_to_rgba};
