#include "app_helpers.h"

#include "ccf/ds/logger.h"

#include <openssl/bio.h>
#include <openssl/evp.h>

namespace app
{
  std::vector<unsigned char> base64_decode(const std::string& input)
  {
    BIO* bio = nullptr;
    BIO* b64 = nullptr;
    std::vector<unsigned char> buffer(input.size());

    bio = BIO_new_mem_buf(input.c_str(), -1);
    b64 = BIO_new(BIO_f_base64());
    bio = BIO_push(b64, bio);
    BIO_read(bio, buffer.data(), static_cast<int>(buffer.size()));
    BIO_free_all(bio);

    return buffer;
  }

  double process_weights(const std::vector<unsigned char>& binary_weights)
  {
    double weight_sum = 0.0;
    for (const auto& weight : binary_weights)
    {
      weight_sum += static_cast<double>(weight);
    }
    return weight_sum;
  }
}
