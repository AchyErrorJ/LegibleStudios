#pragma once
/**
 * @file llm_assistant.hpp
 * @brief LLM Assistant for render tuning via local LM Studio API
 */

#include <string>
#include <vector>
#include <thread>
#include <mutex>

namespace arch {

/**
 * @brief Snapshot of current rendering state for LLM context
 */
struct RenderStateSnapshot {
    float iblIntensity = 1.0f;
    float iblDiffuseIntensity = 1.0f;
    float iblSpecularIntensity = 1.0f;
    float fresnelIntensity = 1.0f;
    bool iblEnabled = true;

    float exposure = 1.0f;
    float bloomIntensity = 0.5f;
    float bloomThreshold = 1.0f;
    bool bloomEnabled = true;
    float ssaoIntensity = 1.0f;
    float ssaoRadius = 0.5f;
    bool ssaoEnabled = true;

    float defaultRoughness = 0.5f;
    float defaultMetallic = 0.0f;

    bool directLightEnabled = true;
    bool normalMappingEnabled = true;

    std::string toJson() const;
};

/**
 * @brief Single parameter change suggestion
 */
struct ParameterSuggestion {
    std::string paramName;
    std::string displayName;
    float currentValue = 0.0f;
    float suggestedValue = 0.0f;
    std::string reason;
};

/**
 * @brief Chat message with role and content
 */
struct ChatMessage {
    enum class Role {
        User,
        Assistant
    };

    Role role = Role::User;
    std::string content;
    std::vector<ParameterSuggestion> suggestions;

    bool hasSuggestions() const { return !suggestions.empty(); }
};

/**
 * @brief LLM Assistant for render tuning
 *
 * Communicates with local LM Studio via OpenAI-compatible API.
 */
class LLMAssistant {
public:
    LLMAssistant();
    ~LLMAssistant();

    // Connection settings
    void setEndpoint(const std::string& host, int port);
    void setModel(const std::string& model);
    bool testConnection();
    bool isConnected() const;

    // Messaging
    void sendMessage(const std::string& userMessage, const RenderStateSnapshot& state);
    bool hasResponse() const;
    ChatMessage getLatestResponse();
    const std::vector<ChatMessage>& getChatHistory() const { return m_chatHistory; }
    bool isProcessing() const { return m_processing; }
    void clearHistory();

    // Status
    const std::string& getStatus() const { return m_status; }
    const std::string& getLastError() const { return m_lastError; }

private:
    std::string buildSystemPrompt() const;
    std::string buildUserPrompt(const std::string& userMessage, const RenderStateSnapshot& state) const;
    void processRequest(const std::string& prompt);
    std::vector<ParameterSuggestion> parseSuggestions(const std::string& response, const RenderStateSnapshot& state);

    std::string m_host = "localhost";
    int m_port = 1234;
    std::string m_model = "local-model";
    std::string m_status = "Ready";
    std::string m_lastError;

    bool m_processing = false;
    bool m_hasNewResponse = false;

    std::vector<ChatMessage> m_chatHistory;
    ChatMessage m_latestResponse;

    mutable std::mutex m_mutex;
    std::thread m_requestThread;
};

} // namespace arch
