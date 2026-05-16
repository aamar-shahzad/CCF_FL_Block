#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <vector>

namespace app::aggregation
{
  enum class AggregationMethod
  {
    FedAvg,
    Ahda,
    Krum,
    He
  };

  inline AggregationMethod parse_method(const std::string& s)
  {
    if (s == "fedavg" || s == "FedAvg")
      return AggregationMethod::FedAvg;
    if (s == "krum" || s == "Krum")
      return AggregationMethod::Krum;
    if (s == "he" || s == "he_fedavg" || s == "he_based")
      return AggregationMethod::He;
    return AggregationMethod::Ahda;
  }

  struct AhdaConfig
  {
    double k_sigma = 2.5;
    bool use_adaptive_threshold = true;
    double fixed_threshold = -1.0;
  };

  struct AggregationResult
  {
    std::vector<float> global_weights;
    std::vector<size_t> accepted_indices;
    std::vector<size_t> rejected_indices;
    std::vector<double> mean_distances;
    double threshold = 0.0;
    std::string method;
    int64_t elapsed_ms = 0;
    size_t partition_count = 1;
  };

  inline nlohmann::json to_json(const AggregationResult& r)
  {
    return nlohmann::json{
      {"method", r.method},
      {"threshold", r.threshold},
      {"accepted_indices", r.accepted_indices},
      {"rejected_indices", r.rejected_indices},
      {"mean_distances", r.mean_distances},
      {"elapsed_ms", r.elapsed_ms},
      {"partition_count", r.partition_count},
      {"num_accepted", r.accepted_indices.size()},
      {"num_rejected", r.rejected_indices.size()}};
  }
}
