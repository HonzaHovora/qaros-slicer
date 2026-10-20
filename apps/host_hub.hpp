#pragma once
#include <qar_streaming.h>
#include <cstring>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace qarvtk {
struct HostTarget {
  QarPeerId id{};
  QarPeerRole role{};
  QarDeviceCategory category{};
  QarAppState state{};
  std::string name;
};

// A Visualizer's control peer is not a receiver. Never negotiate frames with
// a source, infrastructure, an initializing target, or an arbitrary first peer.
inline std::optional<HostTarget> select_host_target(const std::vector<HostTarget>& peers,
                                                   QarDeviceCategory category) {
  std::optional<HostTarget> selected;
  for (const auto& peer : peers) {
    if (peer.role != QAR_PEER_ROLE_TARGET || peer.state != QAR_APP_STATE_RUNNING ||
        peer.category != category) continue;
    if (selected && std::memcmp(selected->id.data, peer.id.data, sizeof(peer.id.data)) != 0)
      throw std::runtime_error("Several matching QAROS receivers are running. Keep one receiver of the selected type running, then restart streaming.");
    selected = peer;
  }
  return selected;
}

// Common names are ASCII identities, not display labels. Include this source
// peer so a second Slicer process, duplicate labels or Unicode names cannot
// reuse another source's volume/panel and close it during teardown.
inline std::string host_resource_name(const QarPeerId& source, const char* kind, std::size_t index) {
  static constexpr char hex[] = "0123456789abcdef";
  std::string name = "slicer-";
  for (auto byte : source.data) { name += hex[byte >> 4]; name += hex[byte & 15]; }
  return name + '-' + kind + '-' + std::to_string(index);
}
}
