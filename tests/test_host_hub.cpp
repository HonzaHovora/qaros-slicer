#if !defined(_WIN32) && defined(__GNUC__)
#define __declspec(annotation)
#endif
#include "../apps/host_hub.hpp"
#undef NDEBUG
#include <cassert>
#include <iostream>

int main() {
  using namespace qarvtk;
  HostTarget viewer{{}, QAR_PEER_ROLE_TARGET, QAR_DEVICE_CATEGORY_VISUALIZER, QAR_APP_STATE_RUNNING, "Viewer"};
  viewer.id.data[0] = 1;
  auto control = viewer; control.id.data[0] = 2; control.role = QAR_PEER_ROLE_CONTROL;
  auto source = viewer; source.id.data[0] = 3; source.role = QAR_PEER_ROLE_SOURCE;
  auto internal = viewer; internal.id.data[0] = 4; internal.role = QAR_PEER_ROLE_INTERNAL;
  auto headset = viewer; headset.id.data[0] = 5; headset.category = QAR_DEVICE_CATEGORY_HEADSET;
  for (auto state : {QAR_APP_STATE_UNKNOWN, QAR_APP_STATE_INITIALIZING, QAR_APP_STATE_SHUTTING_DOWN, QAR_APP_STATE_RETIRED}) {
    auto inactive = viewer; inactive.state = state;
    assert(!select_host_target({control, source, internal, inactive, headset}, QAR_DEVICE_CATEGORY_VISUALIZER));
  }
  auto selected = select_host_target({control, source, internal, viewer, headset}, QAR_DEVICE_CATEGORY_VISUALIZER);
  assert(selected && selected->id.data[0] == 1);
  selected = select_host_target({control, viewer, headset}, QAR_DEVICE_CATEGORY_HEADSET);
  assert(selected && selected->id.data[0] == 5);
  auto other = viewer; other.id.data[15] = 1;
  bool ambiguous = false;
  try { select_host_target({viewer, other}, QAR_DEVICE_CATEGORY_VISUALIZER); }
  catch (const std::runtime_error&) { ambiguous = true; }
  assert(ambiguous);
  assert(select_host_target({viewer, viewer}, QAR_DEVICE_CATEGORY_VISUALIZER));
  const auto key = host_resource_name(viewer.id, "volume", 0);
  assert(key != host_resource_name(viewer.id, "volume", 1));
  assert(key != host_resource_name(other.id, "volume", 0));
  assert(key != host_resource_name(viewer.id, "panel", 0));
  for (unsigned char c : key) assert(c < 128);
  std::cout << "PASS: only running targets; category filtering; ambiguity; isolated volume/panel identities\n";
}
