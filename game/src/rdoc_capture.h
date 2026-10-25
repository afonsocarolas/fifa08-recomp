#pragma once

#ifndef _WIN32
// Windows-only debugging tool; no-op elsewhere (Android build).
namespace fifa08 {
inline void StartTimedRenderDocCaptures() {}
}  // namespace fifa08
#else

// Timed RenderDoc frame captures for debugging, e.g.
//   renderdoccmd capture fifa08.exe ... --rdoc_capture_at=44,48,52 --rdoc_capture_path=C:\caps\port
// Does nothing unless the game was started under RenderDoc and rdoc_capture_at is set.

#include <chrono>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include <windows.h>

#include <renderdoc/renderdoc_app.h>  // SDK ships API 1.0 (capture path setter is "SetLogFilePathTemplate")
#include <rex/cvar.h>

REXCVAR_DEFINE_STRING(rdoc_capture_at, "", "Debug",
                      "Comma-separated seconds after start at which to take a RenderDoc capture");
REXCVAR_DEFINE_STRING(rdoc_capture_path, "", "Debug",
                      "RenderDoc capture file path template (frame number is appended)");

namespace fifa08 {

inline void StartTimedRenderDocCaptures() {
  std::string at = REXCVAR_GET(rdoc_capture_at);
  if (at.empty()) return;
  HMODULE module = GetModuleHandleA("renderdoc.dll");
  if (!module) return;  // not running under RenderDoc
  auto get_api = reinterpret_cast<pRENDERDOC_GetAPI>(GetProcAddress(module, "RENDERDOC_GetAPI"));
  RENDERDOC_API_1_0_0* api = nullptr;
  if (!get_api || !get_api(eRENDERDOC_API_Version_1_0_0, reinterpret_cast<void**>(&api))) return;

  std::string path = REXCVAR_GET(rdoc_capture_path);
  if (!path.empty()) api->SetLogFilePathTemplate(path.c_str());

  std::vector<int> seconds;
  std::stringstream list(at);
  for (std::string item; std::getline(list, item, ',');) seconds.push_back(std::stoi(item));

  // RenderDoc's own trigger captures one host present, which holds only the
  // presenter's work. gpu_capture_next_frame (SDK patch) brackets a whole
  // guest frame instead.
  std::thread([seconds] {
    auto start = std::chrono::steady_clock::now();
    for (int s : seconds) {
      std::this_thread::sleep_until(start + std::chrono::seconds(s));
      rex::cvar::SetFlagByName("gpu_capture_next_frame", "true");
    }
  }).detach();
}

}  // namespace fifa08

#endif  // _WIN32
