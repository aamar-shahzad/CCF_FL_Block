#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <vector>

namespace app
{
  std::vector<unsigned char> base64_decode(const std::string& input);
  double process_weights(const std::vector<unsigned char>& binary_weights);
}
