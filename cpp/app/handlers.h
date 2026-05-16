#pragma once

#include "ccf/json_handler.h"

namespace app
{
  ccf::HandlerJsonParamsAndForward write_user_handler();
  ccf::HandlerJsonParamsAndForward write_model_handler();
  ccf::HandlerJsonParamsAndForward write_weights_handler();
  ccf::HandlerJsonParamsAndForward register_client_handler();
  ccf::ReadOnlyHandlerWithJson get_aggregate_stats_handler();
  ccf::ReadOnlyHandlerWithJson get_global_model_handler();
  ccf::ReadOnlyHandlerWithJson get_model_handler();
  ccf::HandlerJsonParamsAndForward aggregate_weights_federated_handler();
}
