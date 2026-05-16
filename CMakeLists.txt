cmake_minimum_required(VERSION 3.16)

include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/version.cmake)

project(
  lskv
  LANGUAGES C CXX
  VERSION ${LSKV_VERSION_SHORT})

set(Boost_MAJOR_VERSION 1)
set(Boost_MINOR_VERSION 71)
set(Boost_VERSION ${Boost_MAJOR_VERSION}.${Boost_MINOR_VERSION}.0)
  
set(CCF "ccf_virtual")
set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS ON)
set(Boost_USE_STATIC_RUNTIME OFF)

find_package(Boost REQUIRED COMPONENTS log)
if(Boost_FOUND)
    include_directories(${Boost_INCLUDE_DIRS})
endif()

if(EXISTS "${CMAKE_SOURCE_DIR}/3rdparty/NumCpp/include")
  include_directories(3rdparty/NumCpp/include)
endif()

option(CCF_UNSAFE "build with unsafe options" OFF)
if(${CCF_UNSAFE})
  if(${COMPILE_TARGET} STREQUAL "sgx")
    message(WARNING "Building with unsafe options")
    set(CCF "${CCF}_unsafe")
  else()
    message(
      FATAL_ERROR "CCF_UNSAFE is not support for target ${COMPILE_TARGET}")
  endif()
endif()

if(NOT TARGET ${CCF})
  find_package(${CCF} REQUIRED)
endif()







option(VERBOSE_LOGGING "enable verbose logging" OFF)

add_compile_definitions(LSKV_VERSION="${LSKV_VERSION}")



add_ccf_app(
  lskv
  SRCS
  cpp/app/app.cpp
  cpp/app/handlers_aggregate.cpp
  cpp/app/handlers_model.cpp
  cpp/app/offchain_store.cpp
  INCLUDE_DIRS
  "${CMAKE_CURRENT_SOURCE_DIR}/cpp/app"
  "${CCF_DIR}/include/ccf/_private"
  INSTALL_LIBS
  ON)

if(VERBOSE_LOGGING)
  message(STATUS "Using verbose logging")
  add_compile_definitions(VERBOSE_LOGGING)
else()
  message(STATUS "Using terse logging")
endif()



# Generate an ephemeral signing key
add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/signing_key.pem
  COMMAND openssl genrsa -out ${CMAKE_CURRENT_BINARY_DIR}/signing_key.pem -3
          3072)
add_custom_target(app_signing_key ALL
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/signing_key.pem)

sign_app_library(lskv.enclave ${CMAKE_CURRENT_SOURCE_DIR}/oe_sign.conf
                 ${CMAKE_CURRENT_BINARY_DIR}/signing_key.pem INSTALL_LIBS ON)






