#pragma once

#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <vector>

namespace app::offchain
{
  constexpr const char* DEFAULT_ROOT = "data/offchain";

  std::string sha256_hex(const std::string& data);

  std::string store_weights(
    const nlohmann::json& weights,
    const std::string& root = DEFAULT_ROOT);

  std::optional<std::vector<float>> load_weights(
    const std::string& weight_ref, const std::string& root = DEFAULT_ROOT);

  std::optional<nlohmann::json> load_json(
    const std::string& weight_ref, const std::string& root = DEFAULT_ROOT);
}
