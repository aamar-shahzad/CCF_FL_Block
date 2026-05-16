// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ccf/app_interface.h"
#include "ccf/common_auth_policies.h"
#include "ccf/json_handler.h"

#include "app_types.h"
#include "handlers.h"

namespace app
{
  class AppHandlers : public ccf::UserEndpointRegistry
  {
  public:
    AppHandlers(ccf::AbstractNodeContext& context) :
      ccf::UserEndpointRegistry(context)
    {
      openapi_info.title = "CCF Sample C++ App";
      openapi_info.description =
        "This minimal CCF C++ application aims to be "
        "used as a template for CCF developers.";
      openapi_info.document_version = "0.0.1";

      make_read_only_endpoint(
        "/model/download_gloabl_weights",
        HTTP_GET,
        ccf::json_read_only_adapter(get_global_model_handler()),
        {ccf::user_cert_auth_policy})
        .set_auto_schema<void, nlohmann::json>()
        .add_query_parameter<size_t>("model_id")
        .install();

      make_endpoint(
        "/user/add",
        HTTP_POST,
        ccf::json_adapter(write_user_handler()),
        ccf::no_auth_required)
        .set_auto_schema<Write::In, void>()
        .install();

      make_endpoint(
        "/model/intial_model",
        HTTP_POST,
        ccf::json_adapter(write_model_handler()),
        ccf::no_auth_required)
        .set_auto_schema<ModelWrite::In, void>()
        .install();

      make_endpoint(
        "/model/upload/local_model_weights",
        HTTP_POST,
        ccf::json_adapter(write_weights_handler()),
        {ccf::user_cert_auth_policy})
        .set_auto_schema<ModelWeightWrite::In, void>()
        .install();

      make_endpoint(
        "/model/register_client",
        HTTP_POST,
        ccf::json_adapter(register_client_handler()),
        {ccf::member_cert_auth_policy})
        .set_auto_schema<ClientRegister::In, void>()
        .install();

      make_endpoint(
        "/model/aggregate_weights_local",
        HTTP_PUT,
        ccf::json_adapter(aggregate_weights_federated_handler()),
        {ccf::member_cert_auth_policy})
        .add_query_parameter<size_t>("model_id")
        .add_query_parameter<size_t>("round_no")
        .install();

      make_read_only_endpoint(
        "/model/aggregate_stats",
        HTTP_GET,
        ccf::json_read_only_adapter(get_aggregate_stats_handler()),
        {ccf::user_cert_auth_policy})
        .add_query_parameter<size_t>("model_id")
        .add_query_parameter<size_t>("round_no")
        .install();

      make_read_only_endpoint(
        "/model/download/global",
        HTTP_GET,
        ccf::json_read_only_adapter(get_model_handler()),
        {ccf::user_cert_auth_policy})
        .set_auto_schema<void, nlohmann::json>()
        .add_query_parameter<size_t>("model_id")
        .install();
    }
  };
} // namespace app

namespace ccf
{
  std::unique_ptr<ccf::endpoints::EndpointRegistry> make_user_endpoints(
    ccf::AbstractNodeContext& context)
  {
    return std::make_unique<app::AppHandlers>(context);
  }

  std::vector<ccf::js::FFIPlugin> get_js_plugins()
  {
    return {};
  }
}
