#pragma once
#include <qar_streaming.h>
#include <string_view>

namespace qarvtk {
// The session-022c40b6 C API does not expose status 602 or a cause iterator.
// Its runtime reports the startup pause as 803 wrapping 602 in result_message.
// Match that precise diagnostic; an arbitrary begin-frame failure stays fatal.
inline bool legacy_begin_frame_paused(QarResult result) {
  if (result.code != QAR_STATUS_RENDERING_PRODUCER_UNABLE_TO_DO_BEGIN_FRAME ||
      !result.error_handle) return false;
  char message[4096]{};
  qar_result_message(result, message, sizeof(message));
  message[sizeof(message)-1] = '\0';
  return std::string_view(message).find(
      "wrapped error: Code: 602 Desc: MediaStreamingStreamIsPaused Msg:") !=
      std::string_view::npos;
}
} // namespace qarvtk
