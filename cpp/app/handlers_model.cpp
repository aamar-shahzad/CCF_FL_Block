#include "handlers.h"

#include "app_common.h"
#include "app_types.h"
#include "ccf/ds/logger.h"
#include "ccf/http_query.h"
#include "offchain_store.h"

#include <fmt/format.h>

namespace http = ccf::http;

namespace app
{
  ccf::HandlerJsonParamsAndForward write_user_handler()
  {
    return [](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
      const auto in = params.get<Write::In>();
      if (in.msg.empty())
      {
        return ccf::make_error(
          HTTP_STATUS_BAD_REQUEST,
          ccf::errors::InvalidInput,
          "Cannot record an empty user message.");
      }
      auto users_handle = ctx.tx.template rw<User>(USERS);
      users_handle->put(users_handle->size(), in.msg);
      return ccf::make_success();
    };
  }

  ccf::HandlerJsonParamsAndForward write_model_handler()
  {
    return [](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
      try
      {
        CCF_APP_INFO("uploading endpoint called");
        const auto in = params.get<ModelWrite::In>();
        const GlobalModel& global_model = in.global_model;

        if (
          global_model.model_name.empty() || global_model.model_data.is_null())
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidInput,
            "Invalid or empty model payload.");
        }

        auto models_handle = ctx.tx.template rw<Model>(MODELS);
        const size_t model_id = models_handle->size();
        models_handle->put(model_id, global_model.model_data);

        CCF_APP_INFO(
          "Model ID: {}, Model Name: {}",
          model_id,
          global_model.model_name);

        return ccf::make_success(nlohmann::json{
          {"model_id", model_id},
          {"message", "Model uploaded successfully"},
          {"model_name", global_model.model_name}});
      }
      catch (const std::exception& e)
      {
        CCF_APP_INFO("Exception in write_model: {}", e.what());
        return ccf::make_error(
          HTTP_STATUS_INTERNAL_SERVER_ERROR,
          ccf::errors::InternalError,
          "Internal server error occurred while processing the request.");
      }
    };
  }

  ccf::HandlerJsonParamsAndForward write_weights_handler()
  {
    return [](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
      try
      {
        CCF_APP_INFO("model weight write endpoint called");
        auto weights_handle = ctx.tx.template rw<Weights>(WEIGHTS);
        const auto in = params.get<ModelWeightWrite::In>();
        const bool has_he =
          in.weights_json.is_object() && in.weights_json.value("he", false);
        const bool has_inline =
          !has_he && !in.weights_json.is_null() &&
          in.weights_json.is_array() && !in.weights_json.empty();
        const bool has_ref = !in.weight_ref.empty();
        if (!has_inline && !has_ref && !has_he)
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidInput,
            "Provide weights_json or weight_ref.");
        }

        const size_t round_no = in.round_no;
        auto model_weight = in.weights_json;
        const size_t model_id = in.model_id;

        if (!in.client_id.empty())
        {
          auto registry = ctx.tx.template ro<ClientRegistry>(CLIENT_REGISTRY);
          if (!registry->get(in.client_id).has_value())
          {
            return ccf::make_error(
              HTTP_STATUS_FORBIDDEN,
              ccf::errors::AuthorizationFailed,
              "Client not registered. Use /model/register_client first.");
          }
          bool duplicate = false;
          weights_handle->foreach(
            [&](const size_t&, const nlohmann::json& existing) -> bool {
              if (
                existing.contains("client_id") &&
                existing["client_id"] == in.client_id &&
                existing["model_id"].get<size_t>() == model_id &&
                existing["round_no"].get<size_t>() == round_no)
              {
                duplicate = true;
                return false;
              }
              return true;
            });
          if (duplicate)
          {
            return ccf::make_error(
              HTTP_STATUS_CONFLICT,
              ccf::errors::PreconditionFailed,
              "Update already submitted for this client and round.");
          }
        }

        std::string weight_ref = in.weight_ref;
        std::string weight_hash = in.weight_hash;
        nlohmann::json stored_weight = model_weight;

        if (has_he)
        {
          stored_weight = in.weights_json;
        }
        else if (!model_weight.is_null() && model_weight.is_array())
        {
          if (weight_hash.empty())
            weight_hash = offchain::sha256_hex(model_weight.dump());
          if (weight_ref.empty())
            weight_ref = offchain::store_weights(model_weight);
          // Keep a copy on-ledger: virtual enclave FS may not share host paths, so
          // aggregation must not rely on offchain::load_weights alone.
          stored_weight = model_weight;
        }

        nlohmann::json serializedObject = {
          {"round_no", round_no},
          {"model_id", model_id},
          {"client_id", in.client_id},
          {"weight_hash", weight_hash},
          {"weight_ref", weight_ref}};
        if (!stored_weight.is_null())
          serializedObject["model_weight"] = stored_weight;

        weights_handle->put(weights_handle->size(), serializedObject);
        return ccf::make_success(
          nlohmann::json{{"message", "Model weights received"}});
      }
      catch (const std::exception& e)
      {
        CCF_APP_INFO("Exception in write_weights: {}", e.what());
        return ccf::make_error(
          HTTP_STATUS_INTERNAL_SERVER_ERROR,
          ccf::errors::InternalError,
          "Internal server error occurred while processing the request.");
      }
    };
  }

  ccf::HandlerJsonParamsAndForward register_client_handler()
  {
    return [](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
      const auto in = params.get<ClientRegister::In>();
      if (in.client_id.empty())
      {
        return ccf::make_error(
          HTTP_STATUS_BAD_REQUEST,
          ccf::errors::InvalidInput,
          "client_id is required.");
      }
      auto registry = ctx.tx.template rw<ClientRegistry>(CLIENT_REGISTRY);
      if (registry->get(in.client_id).has_value())
      {
        return ccf::make_error(
          HTTP_STATUS_CONFLICT,
          ccf::errors::PreconditionFailed,
          "client_id already registered.");
      }
      registry->put(
        in.client_id,
        nlohmann::json{
          {"client_id", in.client_id},
          {"cert_fingerprint", in.cert_fingerprint}});
      return ccf::make_success(
        nlohmann::json{{"client_id", in.client_id}, {"registered", true}});
    };
  }

  ccf::ReadOnlyHandlerWithJson get_aggregate_stats_handler()
  {
    return [](ccf::endpoints::ReadOnlyEndpointContext& ctx, nlohmann::json&&) {
      const auto parsed_query =
        http::parse_query(ctx.rpc_ctx->get_request_query());
      std::string error_reason;
      size_t model_id = 0;
      size_t round_no = 0;
      if (
        !http::get_query_value(
          parsed_query, "model_id", model_id, error_reason) ||
        !http::get_query_value(
          parsed_query, "round_no", round_no, error_reason))
      {
        return ccf::make_error(
          HTTP_STATUS_BAD_REQUEST,
          ccf::errors::InvalidQueryParameterValue,
          std::move(error_reason));
      }
      auto stats_handle = ctx.tx.template ro<AggregateStatsMap>(AGGREGATE_STATS);
      const std::string stats_key = fmt::format("{}_{}", model_id, round_no);
      auto stats = stats_handle->get(stats_key);
      if (!stats.has_value())
      {
        return ccf::make_error(
          HTTP_STATUS_NOT_FOUND,
          ccf::errors::ResourceNotFound,
          "No aggregation stats for this round.");
      }
      return ccf::make_success(stats.value());
    };
  }

  ccf::ReadOnlyHandlerWithJson get_global_model_handler()
  {
    return [](ccf::endpoints::ReadOnlyEndpointContext& ctx, nlohmann::json&&) {
      const auto parsed_query =
        http::parse_query(ctx.rpc_ctx->get_request_query());
      std::string error_reason;
      size_t model_id = 0;
      if (!http::get_query_value(
            parsed_query, "model_id", model_id, error_reason))
      {
        return ccf::make_error(
          HTTP_STATUS_BAD_REQUEST,
          ccf::errors::InvalidQueryParameterValue,
          std::move(error_reason));
      }

      auto global_models_handle =
        ctx.tx.template ro<GlobalModelWeights>(GLOBAL_MODELS);
      auto global_model_entry = global_models_handle->get(model_id);

      if (!global_model_entry.has_value())
      {
        return ccf::make_error(
          HTTP_STATUS_NOT_FOUND,
          ccf::errors::ResourceNotFound,
          fmt::format("Cannot find global model for id \"{}\".", model_id));
      }

      return ccf::make_success(nlohmann::json{
        {"model_id", model_id},
        {"message", "Global model retrieved successfully"},
        {"global_model", std::move(global_model_entry.value())}});
    };
  }

  ccf::ReadOnlyHandlerWithJson get_model_handler()
  {
    return [](ccf::endpoints::ReadOnlyEndpointContext& ctx, nlohmann::json&&) {
      const auto parsed_query =
        http::parse_query(ctx.rpc_ctx->get_request_query());
      std::string error_reason;
      size_t model_id = 0;
      if (!http::get_query_value(
            parsed_query, "model_id", model_id, error_reason))
      {
        return ccf::make_error(
          HTTP_STATUS_BAD_REQUEST,
          ccf::errors::InvalidQueryParameterValue,
          std::move(error_reason));
      }

      auto models_handle = ctx.tx.template ro<Model>(MODELS);
      auto model_json = models_handle->get(model_id);
      if (!model_json.has_value())
      {
        return ccf::make_error(
          HTTP_STATUS_NOT_FOUND,
          ccf::errors::ResourceNotFound,
          fmt::format("Cannot find model for id \"{}\".", model_id));
      }

      return ccf::make_success(nlohmann::json{
        {"model_id", model_id},
        {"message", "Model details retrieved successfully"},
        {"model_details", std::move(model_json.value())}});
    };
  }
}
