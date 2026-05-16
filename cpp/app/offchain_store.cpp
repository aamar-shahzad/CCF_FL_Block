#include "offchain_store.h"

#include <cerrno>
#include <fstream>
#include <iomanip>
#include <openssl/evp.h>
#include <sstream>
#include <sys/stat.h>

namespace app::offchain
{
  static bool ensure_dir(const std::string& path)
  {
    struct stat st {};
    if (stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode))
      return true;
    return mkdir(path.c_str(), 0755) == 0 || errno == EEXIST;
  }

  std::string sha256_hex(const std::string& data)
  {
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
    EVP_DigestUpdate(ctx, data.data(), data.size());
    EVP_DigestFinal_ex(ctx, hash, &len);
    EVP_MD_CTX_free(ctx);

    std::ostringstream oss;
    for (unsigned int i = 0; i < len; ++i)
      oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(hash[i]);
    return oss.str();
  }

  std::string store_weights(
    const nlohmann::json& weights, const std::string& root)
  {
    ensure_dir(root);
    const std::string payload = weights.dump();
    const std::string hash = sha256_hex(payload);
    const std::string path = root + "/" + hash + ".json";
    std::ofstream out(path);
    out << payload;
    return "offchain://" + hash;
  }

  static std::string ref_to_path(const std::string& weight_ref, const std::string& root)
  {
    const std::string prefix = "offchain://";
    if (weight_ref.rfind(prefix, 0) == 0)
      return root + "/" + weight_ref.substr(prefix.size()) + ".json";
    return weight_ref;
  }

  std::optional<nlohmann::json> load_json(
    const std::string& weight_ref, const std::string& root)
  {
    const std::string path = ref_to_path(weight_ref, root);
    std::ifstream in(path);
    if (!in.good())
      return std::nullopt;
    nlohmann::json j;
    in >> j;
    return j;
  }

  std::optional<std::vector<float>> load_weights(
    const std::string& weight_ref, const std::string& root)
  {
    auto j = load_json(weight_ref, root);
    if (!j.has_value())
      return std::nullopt;
    if (j->is_array())
      return j->get<std::vector<float>>();
    return std::nullopt;
  }
}
