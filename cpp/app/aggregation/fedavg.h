#pragma once

#include "types.h"

#include <cmath>
#include <vector>

namespace app::aggregation
{
  inline std::vector<float> federated_average(
    const std::vector<std::vector<float>>& updates)
  {
    if (updates.empty())
      return {};

    const size_t dim = updates[0].size();
    std::vector<float> avg(dim, 0.0f);

    for (const auto& u : updates)
    {
      if (u.size() != dim)
        return {};
      for (size_t i = 0; i < dim; ++i)
        avg[i] += u[i];
    }

    const float n = static_cast<float>(updates.size());
    for (size_t i = 0; i < dim; ++i)
      avg[i] /= n;

    return avg;
  }

  inline AggregationResult run_fedavg(
    const std::vector<std::vector<float>>& updates)
  {
    AggregationResult result;
    result.method = "fedavg";
    for (size_t i = 0; i < updates.size(); ++i)
      result.accepted_indices.push_back(i);
    result.global_weights = federated_average(updates);
    return result;
  }
}
