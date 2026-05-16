#pragma once

#include "ccf/ds/json.h"
#include <nlohmann/json.hpp>

namespace app
{
  struct Write
  {
    struct In
    {
      std::string msg;
    };
    using Out = void;
  };

  struct GlobalModel
  {
    std::string model_name;
    nlohmann::json model_data;
  };

  struct ModelWrite
  {
    struct In
    {
      GlobalModel global_model;
    };
    using Out = void;
  };

  struct ModelWeightWrite
  {
    struct In
    {
      size_t model_id;
      nlohmann::json weights_json;
      size_t round_no;
      std::string client_id;
      std::string weight_hash;
      std::string weight_ref;
    };
    using Out = void;
  };

  struct ClientRegister
  {
    struct In
    {
      std::string client_id;
      std::string cert_fingerprint;
    };
    using Out = void;
  };

  DECLARE_JSON_TYPE(ModelWeightWrite::In);
  DECLARE_JSON_REQUIRED_FIELDS(
    ModelWeightWrite::In, model_id, weights_json, round_no);
  DECLARE_JSON_OPTIONAL_FIELDS(
    ModelWeightWrite::In, client_id, weight_hash, weight_ref);

  DECLARE_JSON_TYPE(ClientRegister::In);
  DECLARE_JSON_REQUIRED_FIELDS(ClientRegister::In, client_id, cert_fingerprint);
  DECLARE_JSON_TYPE(Write::In);
  DECLARE_JSON_REQUIRED_FIELDS(Write::In, msg);

  DECLARE_JSON_TYPE(GlobalModel);
  DECLARE_JSON_REQUIRED_FIELDS(GlobalModel, model_name, model_data);

  DECLARE_JSON_TYPE(ModelWrite::In);
  DECLARE_JSON_REQUIRED_FIELDS(ModelWrite::In, global_model);
}
