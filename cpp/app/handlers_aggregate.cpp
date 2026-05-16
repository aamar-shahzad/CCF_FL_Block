#include "handlers.h"

#include "app_common.h"
#include "ccf/http_query.h"
#include "ccf/ds/logger.h"

#include <fmt/format.h>

#include "aggregation/ahda.h"
#include "aggregation/fedavg.h"
#include "aggregation/he_paillier.h"
#include "aggregation/krum.h"
#include "offchain_store.h"

namespace http = ccf::http;

namespace app
{
  ccf::HandlerJsonParamsAndForward aggregate_weights_federated_handler()
  {
    return [](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
      auto start_time = std::chrono::steady_clock::now();
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

      std::string method_str = "ahda";
      http::get_query_value(parsed_query, "method", method_str, error_reason);

      double k_sigma = 2.5;
      std::string k_str;
      if (http::get_query_value(parsed_query, "k_sigma", k_str, error_reason))
        k_sigma = std::stod(k_str);

      bool use_adaptive = true;
      std::string adaptive_str;
      if (http::get_query_value(
            parsed_query, "use_adaptive", adaptive_str, error_reason))
        use_adaptive = (adaptive_str != "0" && adaptive_str != "false");

      bool partitioned = false;
      std::string part_str;
      if (http::get_query_value(parsed_query, "partitioned", part_str, error_reason))
        partitioned = (part_str == "1" || part_str == "true");

      auto weights_handle = ctx.tx.template ro<Weights>(WEIGHTS);
      auto models_handle = ctx.tx.template ro<Model>(MODELS);
      auto global_models_handle =
        ctx.tx.template rw<GlobalModelWeights>(GLOBAL_MODELS);
      auto stats_handle = ctx.tx.template rw<AggregateStatsMap>(AGGREGATE_STATS);

      const auto method = aggregation::parse_method(method_str);

      if (method == aggregation::AggregationMethod::He)
      {
        auto model_meta = models_handle->get(model_id);
        if (!model_meta.has_value() || !model_meta->contains("paillier_n"))
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidInput,
            "Model missing Paillier public key (upload with HE enabled).");
        }
        const std::string n_hex = (*model_meta)["paillier_n"].get<std::string>();
        std::vector<std::vector<std::string>> client_cts;
        int he_scale = 10000;
        weights_handle->foreach(
          [&](const size_t&, const nlohmann::json& wj) -> bool {
            if (
              wj["model_id"].get<size_t>() != model_id ||
              wj["round_no"].get<size_t>() != round_no)
              return true;
            if (!wj.contains("model_weight") || !wj["model_weight"].is_object())
              return true;
            const auto& mw = wj["model_weight"];
            if (!mw.value("he", false) || !mw.contains("ciphertexts"))
              return true;
            if (mw.contains("scale"))
              he_scale = mw["scale"].get<int>();
            client_cts.push_back(
              mw["ciphertexts"].get<std::vector<std::string>>());
            return true;
          });
        if (client_cts.empty())
        {
          return ccf::make_error(
            HTTP_STATUS_NOT_FOUND,
            ccf::errors::ResourceNotFound,
            "No HE ciphertext updates for this round.");
        }
        auto aggregated = aggregation::paillier_aggregate_ciphertexts(
          client_cts, n_hex);
        nlohmann::json he_global = {
          {"he", true},
          {"ciphertexts", aggregated},
          {"scale", he_scale},
          {"dim", aggregated.size()}};
        global_models_handle->put(model_id, he_global);
        const std::string stats_key = fmt::format("{}_{}", model_id, round_no);
        nlohmann::json stats = {
          {"method", "he"},
          {"num_clients", client_cts.size()},
          {"dim", aggregated.size()}};
        stats_handle->put(stats_key, stats);
        return ccf::make_success(nlohmann::json{
          {"model_id", model_id},
          {"round_no", round_no},
          {"message", "HE aggregation complete"},
          {"aggregation", stats}});
      }

      std::vector<std::vector<float>> flattenedUpdates;
      weights_handle->foreach(
        [&](const size_t&, const nlohmann::json& weights_json) -> bool {
          try
          {
            if (
              weights_json["model_id"].get<size_t>() != model_id ||
              weights_json["round_no"].get<size_t>() != round_no)
              return true;

            std::vector<float> vec;
            if (weights_json.contains("model_weight") &&
                weights_json["model_weight"].is_array())
            {
              vec = weights_json["model_weight"].get<std::vector<float>>();
            }
            else if (weights_json.contains("weight_ref"))
            {
              auto loaded = offchain::load_weights(
                weights_json["weight_ref"].get<std::string>());
              if (!loaded.has_value())
                return true;
              vec = std::move(loaded.value());
            }
            if (!vec.empty())
              flattenedUpdates.push_back(std::move(vec));
          }
          catch (const std::exception& e)
          {
            CCF_APP_INFO("Error processing weights: {}", e.what());
          }
          return true;
        });

      if (flattenedUpdates.empty())
      {
        return ccf::make_error(
          HTTP_STATUS_NOT_FOUND,
          ccf::errors::ResourceNotFound,
          "No weight updates found for this model_id and round_no.");
      }

      try
      {
        aggregation::AhdaConfig ahda_cfg;
        ahda_cfg.k_sigma = k_sigma;
        ahda_cfg.use_adaptive_threshold = use_adaptive;

        aggregation::AggregationResult agg;
        switch (method)
        {
          case aggregation::AggregationMethod::FedAvg:
            agg = aggregation::run_fedavg(flattenedUpdates);
            break;
          case aggregation::AggregationMethod::Krum:
            agg = aggregation::run_krum(flattenedUpdates);
            break;
          default:
            if (partitioned)
              agg = aggregation::run_ahda_partitioned(flattenedUpdates, ahda_cfg);
            else
              agg = aggregation::run_ahda(flattenedUpdates, ahda_cfg);
            break;
        }

        auto end_time = std::chrono::steady_clock::now();
        agg.elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                           end_time - start_time)
                           .count();

        global_models_handle->put(model_id, agg.global_weights);

        const std::string stats_key = fmt::format("{}_{}", model_id, round_no);
        nlohmann::json stats = aggregation::to_json(agg);
        stats["model_id"] = model_id;
        stats["round_no"] = round_no;
        stats_handle->put(stats_key, stats);

        nlohmann::json payload = {
          {"model_id", model_id},
          {"round_no", round_no},
          {"message", "Global model updated successfully"},
          {"aggregation", stats}};
        return ccf::make_success(std::move(payload));
      }
      catch (const std::exception& e)
      {
        CCF_APP_INFO("Exception in aggregate_weights: {}", e.what());
        return ccf::make_error(
          HTTP_STATUS_INTERNAL_SERVER_ERROR,
          ccf::errors::InternalError,
          "Internal server error occurred while processing the request.");
      }
    };
  }
}
