// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ccf/app_interface.h"
#include "ccf/common_auth_policies.h"
#include "ccf/http_query.h"
#include "ccf/json_handler.h"

#include <nlohmann/json.hpp>
#define FMT_HEADER_ONLY
#include "ccf/ds/logger.h"
#include "crypto/entropy.h"
#include "crypto/key_pair.h"
#include "crypto/rsa_key_pair.h"

#include <cstring>
#include <fmt/format.h>
#include <iostream>
#include <numeric>
#include <openssl/bio.h>
#include <openssl/evp.h>
#include <string>
#include <vector>
namespace app
{

  using json = nlohmann::json;
  std::vector<unsigned char> base64_decode(const std::string& input)
  {
    BIO *bio, *b64;
    std::vector<unsigned char> buffer(input.size());

    bio = BIO_new_mem_buf(input.c_str(), -1);
    b64 = BIO_new(BIO_f_base64());
    bio = BIO_push(b64, bio);

    // Decode the base64 string
    BIO_read(bio, buffer.data(), buffer.size());

    BIO_free_all(bio);

    return buffer;
  }
  double process_weights(const std::vector<unsigned char>& binary_weights)
  {
    // Example: Calculate the sum of weights
    double weight_sum = 0.0;

    // Iterate over the binary_weights vector and accumulate the sum
    for (const auto& weight : binary_weights)
    {
      weight_sum += static_cast<double>(weight);
    }

    return weight_sum;
  }
  // Assume a struct to represent model weights
  struct ModelWeights
  {
    nlohmann::json weights;
  };

  // Function to process JSON weights
  ModelWeights process_weights_json(const nlohmann::json& weights_json)
  {
    // Assuming weights are stored as an array in the JSON
    ModelWeights result;
    if (weights_json.is_array())
    {
      CCF_APP_INFO("weights_json are array");
      for (const auto& weight : weights_json)
      {
        if (weight.is_number())
        {
          result.weights.push_back(weight.get<double>());
        }
      }
    }
    return result;
  }
  std::vector<std::vector<double>> deserialize_weights(std::string serialized_weights) {
    // serizlized weights are nest array we need to deserilize it and return the vector of vector of double
    std::vector<std::vector<double>> weights;
    try {
      // Deserialize the weights
      auto deserialized_weights = json::parse(serialized_weights);
      // Check if the deserialized weights are an array
      if (deserialized_weights.is_array()) {
        // Iterate over the array elements
        for (const auto& nested_weights : deserialized_weights) {
          // Check if the nested weights are an array
          if (nested_weights.is_array()) {
            // Initialize a vector to store the nested weights
            std::vector<double> nested_weights_vector;
            // Iterate over the nested array elements
            for (const auto& weight : nested_weights) {
              // Check if the weight is a number
              if (weight.is_number()) {
                // Append the weight to the nested weights vector
                nested_weights_vector.push_back(weight.get<double>());
              }
            }
            // Append the nested weights vector to the weights vector
            weights.push_back(nested_weights_vector);
          }
        }
      }
    }
    catch (const std::exception& e) {
      // Handle exceptions and return an empty vector
      CCF_APP_INFO("Exception in deserialize_weights: {}", e.what());
      return std::vector<std::vector<double>>();
    }
    catch (...) {
      // Handle unknown exceptions and return an empty vector
      CCF_APP_INFO("Unknown exception in deserialize_weights");
      return std::vector<std::vector<double>>();
    }
    
    return weights;
 

    
}

  void add_weighted_local_weights(
    const nlohmann::json& weights,
    double weight_factor,
    ModelWeights& global_model)
  {
    if (weights.is_object())
    {
      for (const auto& entry : weights.items())
      {
        CCF_APP_INFO("weight is object");
        if (!entry.key().empty())
        {
          size_t j = std::stoul(entry.key());
          const double local_weight_value = entry.value().get<double>();
          // If the key doesn't exist in the global model, initialize it to 0
          if (
            global_model.weights.find(std::to_string(j)) ==
            global_model.weights.end())
          {
            global_model.weights[std::to_string(j)] = 0.0;
            CCF_APP_INFO(
              "global_model.weights[std::to_string(j)] is {}",
              global_model.weights[std::to_string(j)]);
          }
          global_model.weights[std::to_string(j)] +=
            weight_factor * local_weight_value;
        }
        else
        {
          CCF_APP_INFO("Empty key in JSON object.");
        }
      }
    }
    else if (weights.is_array())
    {
      CCF_APP_INFO("weight is array");
      for (const auto& nested_weights : weights)
      {
        add_weighted_local_weights(nested_weights, weight_factor, global_model);
      }
    }
  }

  std::string federated_average(
    const std::vector<std::string>& serialized_weights_list,
    const std::vector<size_t>& sample_counts)
  {
    try
    {
      size_t num_models = serialized_weights_list.size();

      // Deserialize the weights
      std::vector<json> deserialized_weights_list;
      for (const auto& serialized_weights : serialized_weights_list)
      {
        deserialized_weights_list.push_back(json::parse(serialized_weights));
      }

      // Calculate the total number of samples
      size_t total_samples = 0;
      for (size_t count : sample_counts)
      {
        total_samples += count;
      }

      // Calculate the weights for each model based on the number of samples
      std::vector<double> weights;
      for (size_t count : sample_counts)
      {
        weights.push_back(static_cast<double>(count) / total_samples);
      }

      // Initialize an empty vector to store the averaged weights
      std::vector<json> averaged_weights;

      // Perform federated averaging
      // Perform federated averaging
      for (size_t i = 0; i < deserialized_weights_list[0].size(); ++i)
      {
        // Iterate over each layer's weights
        json layer_weights;
        for (size_t j = 0; j < num_models; ++j)
        {
          // Access the innermost array elements in a nested loop
          const json& current_json = deserialized_weights_list[j];
          for (size_t k = 0; k < current_json[i].size(); ++k)
          {
            // Explicitly convert JSON value to double before multiplication
            double json_value = current_json[i][k].get<double>();
            CCF_APP_INFO("json_value {}", json_value);
            layer_weights.push_back(weights[j] * json_value);
          }
        }
        averaged_weights.push_back(layer_weights.get<std::vector<double>>());
      }

      // Serialize the averaged weights
      std::string serialized_averaged_weights = json(averaged_weights).dump();

      return serialized_averaged_weights;
    }
    catch (const std::exception& e)
    {
      // Handle exceptions and return an error message
      CCF_APP_INFO("Exception in federated_average: {}", e.what());
      return "Error: Exception occurred during federated averaging";
    }
    catch (...)
    {
      // Handle unknown exceptions and return an error message
      CCF_APP_INFO("Unknown exception in federated_average");
      return "Error: Unknown exception occurred during federated averaging";
    }
  }

  // Key-value store types
  using Map = kv::Map<size_t, std::string>;

  using User = kv::Map<size_t, std::string>; // User information
  using Model = kv::Map<size_t, nlohmann::json>;
  using Weights = kv::Map<size_t, nlohmann::json>; // Model weights
  using GlobalModelWeights = kv::Map<size_t, nlohmann::json>;

  static constexpr auto GLOBAL_MODELS = "global_models";
  static constexpr auto USERS = "users";
  static constexpr auto MODELS = "models";
  static constexpr auto WEIGHTS = "weights";
  static constexpr auto RECORDS = "records";

  // API types
  struct Write
  {
    struct In
    {
      std::string msg; // Change the type to std::string
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
      GlobalModel global_model; // Use the GlobalModel structure in ModelWrite
    };

    using Out = void;
  };

  struct ModelWeightWrite
  {
    struct In
    {
      size_t model_id;
      nlohmann::json weights_json; // Change the type to nlohmann::json
      size_t round_no;
    };

    using Out = void;
  };
  
  DECLARE_JSON_TYPE(ModelWeightWrite::In);
  DECLARE_JSON_REQUIRED_FIELDS(
    ModelWeightWrite::In, model_id, weights_json, round_no);
  DECLARE_JSON_TYPE(Write::In);
  DECLARE_JSON_REQUIRED_FIELDS(Write::In, msg);

  // Declare JSON types for GlobalModel
  DECLARE_JSON_TYPE(GlobalModel);
  DECLARE_JSON_REQUIRED_FIELDS(GlobalModel, model_name, model_data);

  // Declare JSON types for ModelWrite
  DECLARE_JSON_TYPE(ModelWrite::In);
  DECLARE_JSON_REQUIRED_FIELDS(ModelWrite::In, global_model);

  class AppHandlers : public ccf::UserEndpointRegistry
  {


          std::vector<double> compute_weighted_avg_update(
    const std::vector<nlohmann::json>& local_weights,
    const std::vector<size_t>& sample_counts)
  {
    // check the size of local weight and detrime it shape and print using CCF_APP
    CCF_APP_INFO("local_weights.size() :{}", local_weights.size());
    CCF_APP_INFO("sample_counts.size() :{}", sample_counts.size());
    // Check if the sizes of local_weights and sample_counts match
    if (local_weights.size() != sample_counts.size())
    {
      CCF_APP_INFO("local_weights.size() != sample_counts.size()");
      return std::vector<double>();
    }
   
    // parse each local weight and print it using CCF_APP 
    

// create a variable to store the deserialized weights temporarily this will be multi dimentional vector
    std::vector<std::vector<std::vector<double>>> tempweights;

    for (size_t i = 0; i < local_weights.size(); ++i)
    {
     
      std::vector<std::vector<double>> weights = deserialize_weights(local_weights[i]);
      // Check if the weights are empty
      if (weights.empty())
      {
        CCF_APP_INFO("weights.empty()");
        return std::vector<double>();
      }
      else{
        // print the weights using CCF_APP
        // CCF_APP_INFO("weights :{}", json(weights).dump());
        

        tempweights.push_back(weights);

      }

      // check the size of tempweights and detrime it shape and print using CCF_APP
      CCF_APP_INFO("tempweights.size() :{}", tempweights.size());
    
    // iterate the weights at 0 index and print using CCF_APP

// create a multi dimentional vector to store the avg of tempweights[0][l][m] and tempweights[1][l][m]
    std::vector<std::vector<double>> avgweights;

      for (size_t l = 0; l< tempweights[0].size(); ++l)
      {
        if(tempweights[0][l].size()>0){
          for(size_t m = 0; m< tempweights[0][l].size(); ++m){
            // CCF_APP_INFO("tempweights[0][l][m] :{}", tempweights[0][l][m]);
            // compute the aveage of tempweights[0][l][m] and tempweights[1][l][m] and print using CCF_APP
            double avg = (tempweights[0][l][m] + tempweights[1][l][m])/2;
            CCF_APP_INFO("avg :{}", avg);
            // add this 

          }
          
        }
        else{
          CCF_APP_INFO("tempweights[0][l] is empty");
        }
      
      }
      
   
      
   
   
      
  
   


  





    


    }

  


   
 
    return std::vector<double>();
  }
  public:
    AppHandlers(ccfapp::AbstractNodeContext& context) :
      ccf::UserEndpointRegistry(context)
    {
      openapi_info.title = "CCF Federated learing Framework";
      openapi_info.description =
        "This a CCF base blockchain server side  "
        "it securly store the global model and local model protect against "
        "member inferance attacks ";
      openapi_info.document_version = "0.0.1";
      auto write = [this](auto& ctx, nlohmann::json&& params) {
        const auto parsed_query =
          http::parse_query(ctx.rpc_ctx->get_request_query());

        std::string error_reason;
        size_t id = 0;
        if (!http::get_query_value(parsed_query, "id", id, error_reason))
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidQueryParameterValue,
            std::move(error_reason));
        }

        const auto in = params.get<Write::In>();
        if (in.msg.empty())
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidInput,
            "Cannot record an empty log message.");
        }

        auto records_handle = ctx.tx.template rw<Map>(RECORDS);
        records_handle->put(id, in.msg);
        return ccf::make_success();
      };

      auto default_route = [this](ccf::endpoints::EndpointContext& ctx) {
        // Customize the behavior of the default route here
        return ccf::make_success("Welcome to the CCF Sample C++ App!");
      };


      auto read = [this](auto& ctx, nlohmann::json&& params) {
        const auto parsed_query =
          http::parse_query(ctx.rpc_ctx->get_request_query());

        std::string error_reason;
        size_t id = 0;
        if (!http::get_query_value(parsed_query, "id", id, error_reason))
        {
          return ccf::make_error(
            HTTP_STATUS_BAD_REQUEST,
            ccf::errors::InvalidQueryParameterValue,
            std::move(error_reason));
        }

        auto records_handle = ctx.tx.template ro<Map>(RECORDS);
        auto msg = records_handle->get(id);
        if (!msg.has_value())
        {
          return ccf::make_error(
            HTTP_STATUS_NOT_FOUND,
            ccf::errors::ResourceNotFound,
            fmt::format("Cannot find record for id \"{}\".", id));
        }
        return ccf::make_success(msg.value());
      };

      auto write_user =
        [this](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
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

      auto write_model =
        [this](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
          try
          {
            CCF_APP_INFO("uploading endpoint called");
            const auto in =
              params.get<ModelWrite::In>(); // Change the parameter type
            const GlobalModel& global_model = in.global_model;

            if (
              global_model.model_name.empty() ||
              global_model.model_data.is_null())
            {
              return ccf::make_error(
                HTTP_STATUS_BAD_REQUEST,
                ccf::errors::InvalidInput,
                "Invalid or empty model payload.");
            }

            auto models_handle = ctx.tx.template rw<Model>(MODELS);
            size_t model_id = models_handle->size();

            // Save the model data in the Model map
            models_handle->put(model_id, global_model.model_data);

            // Example: Extract and print information from the custom model
            // structure
            std::string model_name = global_model.model_name;
            CCF_APP_INFO("Model ID: {}, Model Name: {}", model_id, model_name);

            nlohmann::json payload = {
              {"model_id", model_id},
              {"message", "Model uploaded successfully"},
              {"model_name", model_name}};

            auto response = ccf::make_success(std::move(payload));
            return response;
          }
          catch (const std::exception& e)
          {
            CCF_APP_INFO("Exception in write_model: {}", e.what());

            // Handle the exception and return an error response
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
          catch (...)
          {
            CCF_APP_INFO("Unknown exception in write_model");

            // Handle the unknown exception and return an error response
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
        };

      auto write_weights =
        [this](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
          try
          {
            CCF_APP_INFO("model weight write endpoint called");
            auto weights_handle = ctx.tx.template rw<Weights>(WEIGHTS);
            const auto in = params.get<ModelWeightWrite::In>();
            if (in.weights_json.is_null())
            {
              return ccf::make_error(
                HTTP_STATUS_BAD_REQUEST,
                ccf::errors::InvalidInput,
                "Invalid or empty weights payload.");
            }
            size_t round_no = in.round_no;
            auto model_weight = in.weights_json;
            size_t model_id = in.model_id;
            nlohmann::json serializedObject = {
              {"round_no", round_no},
              {"model_weight", model_weight},
              {"model_id", model_id}};
            auto serializedString = serializedObject.dump();
            weights_handle->put(weights_handle->size(), serializedObject);
            nlohmann::json payload = {{"message", "Model weights received"}};
            auto response = ccf::make_success(std::move(payload));
            return response;
          }
          catch (const std::exception& e)
          {
            CCF_APP_INFO("Exception in write_weights: {}", e.what());

            // Handle the exception and return an error response
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
          catch (...)
          {
            CCF_APP_INFO("Unknown exception in write_weights");

            // Handle the unknown exception and return an error response
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
        };
      auto aggregate_weights_federated =
        [this](ccf::endpoints::EndpointContext& ctx, nlohmann::json&& params) {
          CCF_APP_INFO("Aggerating FL");
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

          auto weights_handle = ctx.tx.template ro<Weights>(WEIGHTS);
          auto global_models_handle =
            ctx.tx.template rw<GlobalModelWeights>(GLOBAL_MODELS);
          double learning_rate =
            0.1; // You can adjust the learning rate as needed
          std::vector<nlohmann::json> local_weights;
        

          weights_handle->foreach(
            [&](const size_t& weight_id, const nlohmann::json& weights_json)
              -> bool {
              try
              {
                size_t modelId = weights_json["model_id"];
                nlohmann::json model_weight = weights_json["model_weight"];
                size_t roundNo = weights_json["round_no"];
                if (modelId == model_id&& roundNo == round_no)
                {
                  local_weights.push_back(model_weight);
                }
              
              }
              catch (const std::exception& e)
              {
                CCF_APP_INFO("Error processing weights: {}", e.what());
                return false; // Stop the iteration on error
            
              }

              return true;
            });

          try
          {
      
            // Compute the weighted average update
            std::vector<size_t> sample_counts(local_weights.size(), 1);
            std::vector<double> weighted_avg_update =
              compute_weighted_avg_update(local_weights, sample_counts);
           
            // CCF_APP_INFO("weighted_avg_update :{}", weighted_avg_update);
            // // Update the global model
            // auto global_model_entry = global_models_handle->get(model_id);
            // if (!global_model_entry.has_value())
            // {
            //   return ccf::make_error(
            //     HTTP_STATUS_NOT_FOUND,
            //     ccf::errors::ResourceNotFound,
            //     fmt::format(
            //       "Cannot find global model for id \"{}\".", model_id));
            // }
         
        

            return ccf::make_success("Global model updated successfully");
          }
          catch (const std::exception& e)
          {
            CCF_APP_INFO("Exception in aggregate_weights: {}", e.what());
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
          catch (...)
          {
            CCF_APP_INFO("Unknown exception in aggregate_weights");
            return ccf::make_error(
              HTTP_STATUS_INTERNAL_SERVER_ERROR,
              ccf::errors::InternalError,
              "Internal server error occurred while processing the request.");
          }
        };

      auto get_global_model = [this](auto& ctx, nlohmann::json&& params) {
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

        CCF_APP_INFO(
          "weights_handle->size(): {}", global_models_handle->size());
        auto global_model_entry = global_models_handle->get(model_id);

        if (!global_model_entry.has_value())
        {
          return ccf::make_error(
            HTTP_STATUS_NOT_FOUND,
            ccf::errors::ResourceNotFound,
            fmt::format("Cannot find global model for id \"{}\".", model_id));
        }

        nlohmann::json payload = {
          {"model_id", model_id},
          {"message", "Global model retrieved successfully"},
          {"global_model", std::move(global_model_entry.value())}};
        auto response = ccf::make_success(std::move(payload));
        return response;
      };

      auto aggregate_weights = [this](auto& ctx, nlohmann::json&& params) {
        auto start_time = std::chrono::steady_clock::now();

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

        auto weights_handle = ctx.tx.template ro<Weights>(WEIGHTS);

        // Perform aggregations on weights
        double total_weight_sum = 0.0;
        size_t total_weights_count = 0;

        weights_handle->foreach(
          [&](const size_t& weight_id, const std::string& base64_weights)
            -> bool {
            try
            {
              // Check if the weight record is associated with the specified
              // model_id (You may need to adjust your data model accordingly)
              // For example, you might store the model_id in the weight
              // record. Here, I assume the weight_id itself represents the
              // model_id.
              if (weight_id == model_id)
              {
                // Decode base64-encoded weights
                std::vector<unsigned char> binary_weights =
                  base64_decode(base64_weights);

                // Process the weights (you may need to implement a proper
                // processing logic)
                double weight_sum = process_weights(binary_weights);
                CCF_APP_INFO("weight_sum :{}", weight_sum);

                // Accumulate the weights
                total_weight_sum += weight_sum;
                total_weights_count++;
              }
            }
            catch (const std::exception& e)
            {
              // Handle decoding or processing errors
              CCF_APP_INFO("Error processing weights: {}", e.what());
              return false; // Stop the iteration on error
            }

            return true;
          });

        // Calculate the average weight
        double average_weight = (total_weights_count > 0) ?
          total_weight_sum / total_weights_count :
          0.0;
        auto model_data = weights_handle->get(model_id);
        if (!model_data.has_value())
        {
          return ccf::make_error(
            HTTP_STATUS_NOT_FOUND,
            ccf::errors::ResourceNotFound,
            fmt::format("Cannot find model for id \"{}\".", model_id));
        }

        auto models_handle = ctx.tx.template ro<Model>(MODELS);
        auto model_json = models_handle->get(model_id);
        // CCF_APP_INFO("model json {}", model_json.value);

        auto end_time = std::chrono::steady_clock::now();
        auto elapsed_time =
          std::chrono::duration_cast<std::chrono::milliseconds>(
            end_time - start_time)
            .count();

        CCF_APP_INFO("Aggregation Time: {} ms", elapsed_time);

        return ccf::make_success(average_weight);
      };

      auto get_model = [this](auto& ctx, nlohmann::json&& params) {
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
        CCF_APP_INFO("params id {}", model_id);
        auto models_handle = ctx.tx.template ro<Model>(MODELS);
        auto model_json = models_handle->get(model_id);
        if (!model_json.has_value())
        {
          return ccf::make_error(
            HTTP_STATUS_NOT_FOUND,
            ccf::errors::ResourceNotFound,
            fmt::format("Cannot find model for id \"{}\".", model_id));
        }

        nlohmann::json payload = {
          {"model_id", model_id},
          {"message", "Model details retrieved successfully"},
          {"model_details", std::move(model_json)}};
        auto response = ccf::make_success(std::move(payload));
        return response;
      };

      make_read_only_endpoint(
        "/model/download_gloabl_weights",
        HTTP_GET,
        ccf::json_read_only_adapter(get_global_model),
        ccf::no_auth_required)
        .set_auto_schema<void, nlohmann::json>()
        .add_query_parameter<size_t>("model_id")
        .install();

      make_endpoint(
        "/user/add",
        HTTP_POST,
        ccf::json_adapter(write_user),
        ccf::no_auth_required)
        .set_auto_schema<Write::In, void>()
        .install();

      make_endpoint(
        "/model/intial_model",
        HTTP_POST,
        ccf::json_adapter(write_model),
        ccf::no_auth_required)
        .set_auto_schema<ModelWrite::In, void>() // Set auto schema for
        .install();
      make_endpoint(
        "/model/upload/local_model_weights",
        HTTP_POST,
        ccf::json_adapter(write_weights),
        ccf::no_auth_required)
        .set_auto_schema<ModelWeightWrite::In, void>()
        .install();
      make_endpoint(
        "/model/aggregate_weights_local",
        HTTP_PUT,
        ccf::json_adapter(aggregate_weights_federated),
        ccf::no_auth_required)
        .add_query_parameter<size_t>("model_id")
        .install();
      make_read_only_endpoint(
        "/model/download/global",
        HTTP_GET,
        ccf::json_read_only_adapter(get_model),
        ccf::no_auth_required)
        .set_auto_schema<void, nlohmann::json>()
        .add_query_parameter<size_t>("model_id")
        .install();
    }
  };
} // namespace app

namespace ccfapp
{
  std::unique_ptr<ccf::endpoints::EndpointRegistry> make_user_endpoints(
    ccfapp::AbstractNodeContext& context)
  {
    return std::make_unique<app::AppHandlers>(context);
  }
}