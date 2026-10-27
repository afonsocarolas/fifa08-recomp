// fifa08 - ReXGlue Recompiled Project
//
// Customize your app by overriding virtual hooks from rex::ReXApp.

#pragma once

#include <rex/rex_app.h>
#include <rex/system/gpu_plugin.h>

REXCVAR_DEFINE_STRING(gpu_backend, "", "GPU", "Backend inside the GPU plugin: d3d12 or vulkan (empty = any)");

#include "crash_trace.h"
#include "debug_hooks.h"
#include "keyboard_layout.h"
#include "rdoc_capture.h"
#include "touch_controls.h"
#include "write_watch.h"

class Fifa08App : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<Fifa08App>(new Fifa08App(ctx, "fifa08",
        PPCImageConfig));
  }

  // Override virtual hooks for customization:
  // void OnPostInitLogging() override {}
  // --gpu_backend=d3d12|vulkan picks the backend inside the GPU plugin (the SDK
  // always asks for "any", which is D3D12 on Windows).
  void OnPreSetup(rex::RuntimeConfig& config) override {
    std::string backend = REXCVAR_GET(gpu_backend);
    if (!backend.empty() && !config.gpu_plugin.empty())
      config.graphics = rex::system::LoadGpuPlugin(config.gpu_plugin, backend);
    // Before the input system is created, so the keyboard driver starts with it.
    fifa08::keyboard::Apply();
  }
  // void OnLoadXexImage(std::string& xex_image) override {}
  // void OnPostLoadXexImage() override {}
  void OnPostSetup() override {
    fifa08::StartTimedRenderDocCaptures();
    fifa08::watch::Start();
    fifa08::crash_trace::Start();
  }
  // On-screen gamepad on touch screens (Android only; a no-op elsewhere).
  void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override { fifa08::touch::Start(drawer); }
  // std::unique_ptr<rex::ui::ImGuiDialog> CreateAchievementsOverlay() override;
  // std::unique_ptr<rex::ui::AchievementNotificationDialog>
  // CreateAchievementNotificationDialog() override;
  // void OnShutdown() override {}
#ifdef __ANDROID__
  // The default config path is next to libmain.so, which is read-only on
  // Android; keep it with the user data instead.
  void OnConfigurePaths(rex::PathConfig& paths) override {
    if (!paths.user_data_root.empty()) paths.config_path = paths.user_data_root / "fifa08.toml";
  }
#else
  // void OnConfigurePaths(rex::PathConfig& paths) override {}
#endif
};
