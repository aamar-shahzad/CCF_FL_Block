#pragma once

#include "ccf/kv/map.h"
#include <nlohmann/json.hpp>

namespace app
{
  using Map = ccf::kv::Map<size_t, std::string>;
  using User = ccf::kv::Map<size_t, std::string>;
  using Model = ccf::kv::Map<size_t, nlohmann::json>;
  using Weights = ccf::kv::Map<size_t, nlohmann::json>;
  using GlobalModelWeights = ccf::kv::Map<size_t, nlohmann::json>;
  using ClientRegistry = ccf::kv::Map<std::string, nlohmann::json>;
  using AggregateStatsMap = ccf::kv::Map<std::string, nlohmann::json>;

  inline constexpr auto GLOBAL_MODELS = "global_models";
  inline constexpr auto USERS = "users";
  inline constexpr auto MODELS = "models";
  inline constexpr auto WEIGHTS = "weights";
  inline constexpr auto RECORDS = "records";
  inline constexpr auto CLIENT_REGISTRY = "client_registry";
  inline constexpr auto AGGREGATE_STATS = "aggregate_stats";
}
