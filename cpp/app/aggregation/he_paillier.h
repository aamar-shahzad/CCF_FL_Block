#pragma once

#include <openssl/bn.h>

#include <string>
#include <vector>

namespace app::aggregation
{
  // Paillier homomorphic addition: multiply ciphertexts modulo n^2.
  inline std::string paillier_add_hex(
    const std::string& a_hex, const std::string& b_hex, const std::string& n_hex)
  {
    BN_CTX* ctx = BN_CTX_new();
    BIGNUM* a = BN_new();
    BIGNUM* b = BN_new();
    BIGNUM* n = BN_new();
    BIGNUM* n2 = BN_new();
    BIGNUM* res = BN_new();

    BN_hex2bn(&a, a_hex.c_str());
    BN_hex2bn(&b, b_hex.c_str());
    BN_hex2bn(&n, n_hex.c_str());
    BN_sqr(n2, n, ctx);
    BN_mod_mul(res, a, b, n2, ctx);

    char* out_hex = BN_bn2hex(res);
    std::string result(out_hex);
    OPENSSL_free(out_hex);

    BN_free(a);
    BN_free(b);
    BN_free(n);
    BN_free(n2);
    BN_free(res);
    BN_CTX_free(ctx);
    return result;
  }

  inline std::vector<std::string> paillier_aggregate_ciphertexts(
    const std::vector<std::vector<std::string>>& client_ciphertexts,
    const std::string& n_hex)
  {
    if (client_ciphertexts.empty())
      return {};
    const size_t dim = client_ciphertexts[0].size();
    std::vector<std::string> aggregated(dim);
    for (size_t d = 0; d < dim; ++d)
    {
      std::string acc = client_ciphertexts[0][d];
      for (size_t c = 1; c < client_ciphertexts.size(); ++c)
      {
        if (client_ciphertexts[c].size() != dim)
          continue;
        acc = paillier_add_hex(acc, client_ciphertexts[c][d], n_hex);
      }
      aggregated[d] = acc;
    }
    return aggregated;
  }
}
