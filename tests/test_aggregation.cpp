// Standalone AHDA sanity test (compile in devcontainer):
// g++ -std=c++17 -I cpp/app tests/test_aggregation.cpp -o /tmp/test_agg && /tmp/test_agg
#include "aggregation/ahda.h"
#include "aggregation/fedavg.h"

#include <cassert>
#include <iostream>
#include <vector>

int main()
{
  const size_t dim = 32;
  std::vector<std::vector<float>> honest(5, std::vector<float>(dim, 0.1f));
  std::vector<float> outlier(dim, 100.0f);
  std::vector<std::vector<float>> updates = honest;
  updates.push_back(outlier);

  app::aggregation::AhdaConfig cfg;
  cfg.k_sigma = 1.5;
  auto result = app::aggregation::run_ahda(updates, cfg);

  assert(!result.global_weights.empty());
  assert(result.rejected_indices.size() >= 1);
  std::cout << "AHDA test passed: rejected " << result.rejected_indices.size()
            << " update(s), threshold=" << result.threshold << std::endl;
  return 0;
}
