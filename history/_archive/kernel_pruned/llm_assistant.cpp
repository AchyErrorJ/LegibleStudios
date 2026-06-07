#include "llm_assistant.hpp"
#include <nlohmann/json.hpp>
#include <iostream>
#include <sstream>
#include <regex>

// cpp-httplib for HTTP requests (no SSL needed for local LM Studio)
#include <httplib.h>

using json = nlohmann::json;

namespace arch {

std::string RenderStateSnapshot::toJson() const {
    json j;
    j["ibl"] = {
        {"intensity", iblIntensity},
        {"diffuseIntensity", iblDiffuseIntensity},
        {"specularIntensity", iblSpecularIntensity},
        {"fresnelIntensity", fresnelIntensity},
        {"enabled", iblEnabled}
    };
    j["postProcess"] = {
        {"exposure", exposure},
        {"bloomIntensity", bloomIntensity},
        {"bloomThreshold", bloomThreshold},
        {"bloomEnabled", bloomEnabled},
        {"ssaoIntensity", ssaoIntensity},
        {"ssaoRadius", ssaoRadius},
        {"ssaoEnabled", ssaoEnabled}
    };
    j["material"] = {
        {"defaultRoughness", defaultRoughness},
        {"defaultMetallic", defaultMetallic}
    };
    j["effects"] = {
        {"directLightEnabled", directLightEnabled},
        {"normalMappingEnabled", normalMappingEnabled}
    };
    return j.dump(2);
}

LLMAssistant::LLMAssistant() {
    m_status = "Ready";
}

LLMAssistant::~LLMAssistant() {
    if (m_requestThread.joinable()) {
        m_requestThread.join();
    }
}

void LLMAssistant::setEndpoint(const std::string& host, int port) {
    m_host = host;
    m_port = port;
}

void LLMAssistant::setModel(const std::string& model) {
    m_model = model;
}

bool LLMAssistant::testConnection() {
    try {
        httplib::Client cli(m_host, m_port);
        cli.set_connection_timeout(3);
        cli.set_read_timeout(3);

        auto res = cli.Get("/v1/models");
        if (res && res->status == 200) {
            // Parse response to get first available model
            try {
                json response = json::parse(res->body);
                if (response.contains("data") && response["data"].is_array() && !response["data"].empty()) {
                    std::string firstModel = response["data"][0]["id"].get<std::string>();
                    if (m_model == "local-model" || m_model.empty()) {
                        m_model = firstModel;
                    }
                    m_status = "Connected (" + m_model + ")";
                } else {
                    m_status = "Connected to LM Studio";
                }
            } catch (...) {
                m_status = "Connected to LM Studio";
            }
            return true;
        } else {
            m_status = "Connection failed";
            m_lastError = res ? "HTTP " + std::to_string(res->status) : "No response";
            return false;
        }
    } catch (const std::exception& e) {
        m_status = "Connection error";
        m_lastError = e.what();
        return false;
    }
}

bool LLMAssistant::isConnected() const {
    return m_status.find("Connected") != std::string::npos;
}

std::string LLMAssistant::buildSystemPrompt() const {
    return R"(You are a render tuning assistant for ArchEngine, a PBR (Physically Based Rendering) architectural visualization engine.

Your job is to help users tune rendering parameters to achieve the desired look. When users describe visual issues, analyze them and suggest specific parameter changes.

Available parameters you can suggest changes for:
- iblIntensity (0.0-3.0): Overall IBL/ambient light intensity
- iblDiffuseIntensity (0.0-3.0): Diffuse ambient light from environment
- iblSpecularIntensity (0.0-3.0): Specular reflections from environment (reduces "white film" if lowered)
- fresnelIntensity (0.0-2.0): Edge reflectivity (reduces glare at grazing angles if lowered)
- exposure (0.0-5.0): Overall brightness/exposure
- bloomIntensity (0.0-2.0): Glow effect intensity
- bloomThreshold (0.0-5.0): Brightness threshold for bloom
- ssaoIntensity (0.0-3.0): Ambient occlusion darkness
- ssaoRadius (0.1-2.0): AO sampling radius

When suggesting changes, format each suggestion as:
PARAM: paramName | CURRENT: value | SUGGESTED: value | REASON: explanation

Common issues and fixes:
- "White film on surfaces" -> Lower iblSpecularIntensity and/or fresnelIntensity
- "Too bright/washed out" -> Lower exposure or iblIntensity
- "Too dark" -> Increase exposure or iblIntensity
- "Metals look wrong" -> Adjust iblSpecularIntensity
- "Flat looking" -> Increase ssaoIntensity or iblDiffuseIntensity
- "Too much glow" -> Lower bloomIntensity or increase bloomThreshold

Always explain WHY you're suggesting each change in simple terms.)";
}

std::string LLMAssistant::buildUserPrompt(const std::string& userMessage, const RenderStateSnapshot& state) const {
    std::stringstream ss;
    ss << "Current render settings:\n" << state.toJson() << "\n\n";
    ss << "User issue: " << userMessage;
    return ss.str();
}

void LLMAssistant::sendMessage(const std::string& userMessage, const RenderStateSnapshot& state) {
    if (m_processing) {
        m_lastError = "Already processing a request";
        return;
    }

    // Add user message to history
    ChatMessage userMsg;
    userMsg.role = ChatMessage::Role::User;
    userMsg.content = userMessage;
    m_chatHistory.push_back(userMsg);

    // Build the full prompt
    std::string prompt = buildUserPrompt(userMessage, state);

    // Store state for parsing
    RenderStateSnapshot stateCopy = state;

    // Start async request
    if (m_requestThread.joinable()) {
        m_requestThread.join();
    }

    m_processing = true;
    m_status = "Thinking...";

    m_requestThread = std::thread([this, prompt, stateCopy]() {
        processRequest(prompt);

        // Parse suggestions from response
        std::lock_guard<std::mutex> lock(m_mutex);
        if (!m_latestResponse.content.empty()) {
            m_latestResponse.suggestions = parseSuggestions(m_latestResponse.content, stateCopy);
        }
    });
}

void LLMAssistant::processRequest(const std::string& prompt) {
    try {
        httplib::Client cli(m_host, m_port);
        cli.set_connection_timeout(10);
        cli.set_read_timeout(120);  // LLM can take a while

        // Build OpenAI-compatible request
        json requestBody;
        requestBody["model"] = m_model;
        requestBody["messages"] = json::array();
        requestBody["messages"].push_back({
            {"role", "system"},
            {"content", buildSystemPrompt()}
        });

        // Add chat history for context (last 6 messages max)
        size_t startIdx = m_chatHistory.size() > 6 ? m_chatHistory.size() - 6 : 0;
        for (size_t i = startIdx; i < m_chatHistory.size(); ++i) {
            const auto& msg = m_chatHistory[i];
            std::string role = msg.role == ChatMessage::Role::User ? "user" : "assistant";
            requestBody["messages"].push_back({
                {"role", role},
                {"content", msg.content}
            });
        }

        // Add current prompt
        requestBody["messages"].push_back({
            {"role", "user"},
            {"content", prompt}
        });

        requestBody["temperature"] = 0.7;
        requestBody["max_tokens"] = 2048;

        auto res = cli.Post("/v1/chat/completions",
                           requestBody.dump(),
                           "application/json");

        std::lock_guard<std::mutex> lock(m_mutex);

        if (res && res->status == 200) {
            json response = json::parse(res->body);
            auto& message = response["choices"][0]["message"];

            // Handle different model response formats
            std::string content;
            if (message.contains("content") && message["content"].is_string()) {
                content = message["content"].get<std::string>();
            }
            // Some models (like Qwen) use reasoning_content
            if (content.empty() && message.contains("reasoning_content") && message["reasoning_content"].is_string()) {
                content = message["reasoning_content"].get<std::string>();
            }

            if (content.empty()) {
                m_lastError = "Empty response from model";
                m_status = "Error";
            } else {
                m_latestResponse.role = ChatMessage::Role::Assistant;
                m_latestResponse.content = content;
                m_chatHistory.push_back(m_latestResponse);
                m_hasNewResponse = true;
                m_status = "Ready";
            }
        } else {
            m_lastError = res ? "HTTP " + std::to_string(res->status) + ": " + res->body
                              : "No response from LM Studio";
            m_status = "Error";
        }
    } catch (const std::exception& e) {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_lastError = std::string("Request failed: ") + e.what();
        m_status = "Error";
    }

    m_processing = false;
}

std::vector<ParameterSuggestion> LLMAssistant::parseSuggestions(const std::string& response, const RenderStateSnapshot& state) {
    std::vector<ParameterSuggestion> suggestions;

    // Parse lines like: PARAM: paramName | CURRENT: value | SUGGESTED: value | REASON: explanation
    std::regex paramRegex(R"(PARAM:\s*(\w+)\s*\|\s*CURRENT:\s*([\d.]+)\s*\|\s*SUGGESTED:\s*([\d.]+)\s*\|\s*REASON:\s*(.+))");

    std::istringstream stream(response);
    std::string line;
    while (std::getline(stream, line)) {
        std::smatch match;
        if (std::regex_search(line, match, paramRegex)) {
            ParameterSuggestion sug;
            sug.paramName = match[1].str();
            sug.currentValue = std::stof(match[2].str());
            sug.suggestedValue = std::stof(match[3].str());
            sug.reason = match[4].str();

            // Set display name
            if (sug.paramName == "iblIntensity") sug.displayName = "IBL Intensity";
            else if (sug.paramName == "iblDiffuseIntensity") sug.displayName = "Diffuse Intensity";
            else if (sug.paramName == "iblSpecularIntensity") sug.displayName = "Specular Intensity";
            else if (sug.paramName == "fresnelIntensity") sug.displayName = "Fresnel Intensity";
            else if (sug.paramName == "exposure") sug.displayName = "Exposure";
            else if (sug.paramName == "bloomIntensity") sug.displayName = "Bloom Intensity";
            else if (sug.paramName == "bloomThreshold") sug.displayName = "Bloom Threshold";
            else if (sug.paramName == "ssaoIntensity") sug.displayName = "SSAO Intensity";
            else if (sug.paramName == "ssaoRadius") sug.displayName = "SSAO Radius";
            else sug.displayName = sug.paramName;

            suggestions.push_back(sug);
        }
    }

    return suggestions;
}

bool LLMAssistant::hasResponse() const {
    return m_hasNewResponse;
}

ChatMessage LLMAssistant::getLatestResponse() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_hasNewResponse = false;
    return m_latestResponse;
}

void LLMAssistant::clearHistory() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_chatHistory.clear();
    m_latestResponse = ChatMessage{};
    m_hasNewResponse = false;
}

} // namespace arch
