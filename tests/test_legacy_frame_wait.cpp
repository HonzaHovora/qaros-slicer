#if !defined(_WIN32) && defined(__GNUC__)
#define __declspec(annotation)
#endif
#include "../apps/legacy_frame_wait.hpp"
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>

QAR_DEFINE_MODULE_STORAGE(Result, result);
namespace {
std::string diagnostic;
unsigned message_calls{};
void message(QarResult, char* buffer, size_t size) {
  ++message_calls;
  std::snprintf(buffer, size, "%s", diagnostic.c_str());
}
void require(bool value, const char* detail) {
  if (!value) throw std::runtime_error(detail);
}
}
int main() { try {
  g_qar_result_api.result_message = message;
  // Exact failure shape captured on the user's RTX 2070, with no private ids.
  diagnostic = "Code: 803 Desc: RenderingProducerUnableToDoBeginFrame Msg: "
      " [RenderingStreamSenderImpl.hpp:520]\n"
      "\t-> RenderingStreamSenderImpl.hpp:1230\n"
      "\t-> rendering_stream_sender.cpp:1633\n"
      "\t wrapped error: Code: 602 Desc: MediaStreamingStreamIsPaused Msg: "
      "The Primary Transfer is paused. [VideoStreamSenderImpl.hpp:2867]\n"
      "\t-> VideoStreamSenderImpl.hpp:3071";
  const QarResult begin_error{QAR_STATUS_RENDERING_PRODUCER_UNABLE_TO_DO_BEGIN_FRAME, 1};
  require(qarvtk::legacy_begin_frame_paused(begin_error), "captured startup pause is fatal");
  const auto calls = message_calls;
  require(!qarvtk::legacy_begin_frame_paused({QAR_STATUS_SUCCESS, 0}), "success treated as pause");
  require(!qarvtk::legacy_begin_frame_paused({QAR_STATUS_RENDERING_PRODUCER_STREAM_IS_CLOSED, 1}),
          "closed stream retried because of a nested pause");
  require(!qarvtk::legacy_begin_frame_paused({begin_error.code, 0}), "missing diagnostic accepted");
  require(message_calls == calls, "read a diagnostic for a non-candidate result");
  for (const auto* fatal : {
      "Code: 803 Desc: RenderingProducerUnableToDoBeginFrame Msg: unknown failure",
      "wrapped error: Code: 607 Desc: MediaStreamingLayoutChangeFailed Msg: failed",
      "wrapped error: Code: 602 Desc: AnotherError Msg: The Primary Transfer is paused.",
      "wrapped error: Code: 1602 Desc: MediaStreamingStreamIsPaused Msg: failed",
      "", "MediaStreamingStreamIsPaused"}) {
    diagnostic = fatal;
    require(!qarvtk::legacy_begin_frame_paused(begin_error), "unrelated error suppressed");
  }
  std::cout << "PASS: captured 803/602 startup pause; other failures remain fatal\n";
  return 0;
} catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; } }
