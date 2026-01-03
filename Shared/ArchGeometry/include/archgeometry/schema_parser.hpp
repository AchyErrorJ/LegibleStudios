#pragma once
/**
 * @file schema_parser.hpp
 * @brief JSON schema parser for ArchEngine building documents
 */

#include "schema_types.hpp"
#include <string>
#include <optional>
#include <variant>

namespace archgeometry {

/// Parse error information
struct ParseError {
    std::string message;
    int line = -1;
    int column = -1;
};

/// Result type: either success value or error
template<typename T>
using ParseResult = std::variant<T, ParseError>;

/// Check if result is successful
template<typename T>
bool isSuccess(const ParseResult<T>& result) {
    return std::holds_alternative<T>(result);
}

/// Get success value (throws if error)
template<typename T>
const T& getValue(const ParseResult<T>& result) {
    return std::get<T>(result);
}

/// Get error (throws if success)
template<typename T>
const ParseError& getError(const ParseResult<T>& result) {
    return std::get<ParseError>(result);
}

/**
 * @brief Parser for ArchEngine JSON schema
 */
class SchemaParser {
public:
    /// Parse from JSON string
    static ParseResult<SchemaDocument> parseJson(const std::string& json_string);

    /// Parse from file path
    static ParseResult<SchemaDocument> parseFile(const std::string& file_path);

    /// Validate schema structure (basic validation)
    static ParseResult<bool> validate(const SchemaDocument& doc);

    /// Get schema version from JSON without full parse
    static std::string getVersion(const std::string& json_string);

    /// Parse only wall types from JSON
    static ParseResult<std::unordered_map<std::string, WallType>>
    parseWallTypes(const std::string& json_string);
};

} // namespace archgeometry
