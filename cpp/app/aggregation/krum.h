#pragma once

#include "fedavg.h"
#include "types.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace app::aggregation
{
  inline double euclidean_sq(const std::vector<float>& a, const std::vector<float>& b)
  {
    double s = 0.0;
    const size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; ++i)
    {
      const double d = static_cast<double>(a[i]) - static_cast<double>(b[i]);
      s += d * d;
    }
    return s;
  }

  // Multi-Krum: keep the m updates with smallest Krum scores (m = 1 here → single best).
  inline AggregationResult run_krum(
    const std::vector<std::vector<float>>& updates, size_t num_byzantine = 0)
  {
    AggregationResult result;
    result.method = "krum";

    if (updates.empty())
      return result;

    const size_t n = updates.size();
    if (n == 1)
    {
      result.accepted_indices = {0};
      result.global_weights = updates[0];
      return result;
    }

    const size_t f = num_byzantine;
    const size_t k = n - f - 2;
    const size_t use_k = std::max<size_t>(1, std::min(k, n - 1));

    std::vector<double> scores(n, 0.0);
    for (size_t i = 0; i < n; ++i)
    {
      std::vector<double> dists;
      dists.reserve(n - 1);
      for (size_t j = 0; j < n; ++j)
      {
        if (i != j)
          dists.push_back(euclidean_sq(updates[i], updates[j]));
      }
      std::sort(dists.begin(), dists.end());
      const size_t take = std::min(use_k, dists.size());
      scores[i] = std::accumulate(dists.begin(), dists.begin() + take, 0.0);
    }

    const size_t best =
      static_cast<size_t>(std::distance(
        scores.begin(), std::min_element(scores.begin(), scores.end())));

    result.accepted_indices = {best};
    result.global_weights = updates[best];
    result.mean_distances = scores;
    return result;
  }
}
