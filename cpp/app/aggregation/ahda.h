#pragma once

#include "fedavg.h"
#include "types.h"

#include <algorithm>
#include <bitset>
#include <cmath>
#include <numeric>
#include <vector>

namespace app::aggregation
{
  // Sign-bit hash: one bit per weight dimension (paper: binary hash signature).
  inline std::vector<uint64_t> sign_bit_signature(
    const std::vector<float>& weights)
  {
    std::vector<uint64_t> words((weights.size() + 63) / 64, 0);
    for (size_t i = 0; i < weights.size(); ++i)
    {
      if (weights[i] >= 0.0f)
        words[i / 64] |= (uint64_t(1) << (i % 64));
    }
    return words;
  }

  inline int hamming_distance(
    const std::vector<uint64_t>& a, const std::vector<uint64_t>& b)
  {
    if (a.size() != b.size())
      return INT_MAX;
    int dist = 0;
    for (size_t i = 0; i < a.size(); ++i)
      dist += __builtin_popcountll(a[i] ^ b[i]);
    return dist;
  }

  inline double median(std::vector<double> v)
  {
    if (v.empty())
      return 0.0;
    std::sort(v.begin(), v.end());
    const size_t m = v.size() / 2;
    if (v.size() % 2 == 0)
      return (v[m - 1] + v[m]) / 2.0;
    return v[m];
  }

  inline double mad(const std::vector<double>& v, double med)
  {
    if (v.empty())
      return 0.0;
    std::vector<double> dev(v.size());
    for (size_t i = 0; i < v.size(); ++i)
      dev[i] = std::abs(v[i] - med);
    return median(dev);
  }

  inline AggregationResult run_ahda(
    const std::vector<std::vector<float>>& updates, const AhdaConfig& cfg)
  {
    AggregationResult result;
    result.method = "ahda";

    if (updates.empty())
      return result;

    if (updates.size() == 1)
    {
      result.accepted_indices = {0};
      result.global_weights = updates[0];
      return result;
    }

    const size_t n = updates.size();
    std::vector<std::vector<uint64_t>> sigs;
    sigs.reserve(n);
    for (const auto& u : updates)
      sigs.push_back(sign_bit_signature(u));

    result.mean_distances.resize(n, 0.0);
    for (size_t i = 0; i < n; ++i)
    {
      double sum = 0.0;
      for (size_t j = 0; j < n; ++j)
      {
        if (i == j)
          continue;
        sum += hamming_distance(sigs[i], sigs[j]);
      }
      result.mean_distances[i] = sum / static_cast<double>(n - 1);
    }

    if (cfg.use_adaptive_threshold && cfg.fixed_threshold < 0)
    {
      const double med = median(result.mean_distances);
      const double m = mad(result.mean_distances, med);
      result.threshold = med + cfg.k_sigma * m;
    }
    else if (cfg.fixed_threshold >= 0)
    {
      result.threshold = cfg.fixed_threshold;
    }
    else
    {
      result.threshold =
        *std::max_element(result.mean_distances.begin(), result.mean_distances.end());
    }

    std::vector<std::vector<float>> survivors;
    for (size_t i = 0; i < n; ++i)
    {
      if (result.mean_distances[i] <= result.threshold)
      {
        result.accepted_indices.push_back(i);
        survivors.push_back(updates[i]);
      }
      else
      {
        result.rejected_indices.push_back(i);
      }
    }

    if (survivors.empty())
    {
      for (size_t i = 0; i < n; ++i)
        result.accepted_indices.push_back(i);
      result.rejected_indices.clear();
      result.global_weights = federated_average(updates);
    }
    else
    {
      result.global_weights = federated_average(survivors);
    }

    return result;
  }

  // Partitioned AHDA for large models (TEE memory budget).
  inline AggregationResult run_ahda_partitioned(
    const std::vector<std::vector<float>>& updates,
    const AhdaConfig& cfg,
    size_t max_partition_dims = 50000)
  {
    if (updates.empty() || updates[0].empty())
      return {};

    const size_t dim = updates[0].size();
    if (dim <= max_partition_dims)
    {
      auto r = run_ahda(updates, cfg);
      r.partition_count = 1;
      return r;
    }

    AggregationResult merged;
    merged.method = "ahda_partitioned";
    merged.partition_count = (dim + max_partition_dims - 1) / max_partition_dims;
    merged.global_weights.resize(dim, 0.0f);

    std::vector<bool> accepted_mask(updates.size(), true);

    for (size_t p = 0; p < merged.partition_count; ++p)
    {
      const size_t start = p * max_partition_dims;
      const size_t end = std::min(start + max_partition_dims, dim);
      std::vector<std::vector<float>> slice_updates;
      slice_updates.reserve(updates.size());
      for (const auto& u : updates)
      {
        slice_updates.emplace_back(u.begin() + start, u.begin() + end);
      }
      auto part = run_ahda(slice_updates, cfg);
      for (size_t i = 0; i < updates.size(); ++i)
      {
        if (std::find(
              part.rejected_indices.begin(),
              part.rejected_indices.end(),
              i) != part.rejected_indices.end())
          accepted_mask[i] = false;
      }
      for (size_t j = 0; j < part.global_weights.size(); ++j)
        merged.global_weights[start + j] = part.global_weights[j];
    }

    for (size_t i = 0; i < updates.size(); ++i)
    {
      if (accepted_mask[i])
        merged.accepted_indices.push_back(i);
      else
        merged.rejected_indices.push_back(i);
    }
    merged.threshold = 0.0;
    return merged;
  }
}
