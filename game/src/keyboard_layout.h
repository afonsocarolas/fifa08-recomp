#pragma once

// Keyboard play on PC: switches on the SDK's keyboard -> controller emulation
// (mnk_mode) with a WASD layout for FIFA:
//   move W A S D            skill stick  arrow keys
//   A (short pass) Space    B (shoot) K   X (lob/cross) J   Y (through ball) L
//   RT (sprint) Shift       LT Ctrl       LB / RB  Q / E
//   Start Enter             Back Escape, Backspace           D-pad 1 2 3 4
// Only flags still at their compiled-in default are changed, so the config
// file (fifa08.toml) and command-line flags win. --fifa_keyboard=false turns
// it off.

#ifndef _WIN32
namespace fifa08::keyboard {
inline void Apply() {}
}  // namespace fifa08::keyboard
#else

#include <string_view>
#include <utility>

#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_BOOL(fifa_keyboard, true, "Input", "Play with the keyboard (WASD layout for FIFA)");

namespace fifa08::keyboard {

inline void Apply() {
  if (!REXCVAR_GET(fifa_keyboard)) return;
  static constexpr std::pair<std::string_view, std::string_view> kLayout[] = {
      {"mnk_mode", "true"},
      // Shift (sprint) must not stop W/A/S/D, and Shift/Ctrl are bound alone.
      {"mnk_exact_modifiers", "false"},
      {"keybind_lstick_up", "W"},
      {"keybind_lstick_down", "S"},
      {"keybind_lstick_left", "A"},
      {"keybind_lstick_right", "D"},
      {"keybind_lstick_press", ""},
      {"keybind_rstick_up", "Up"},
      {"keybind_rstick_down", "Down"},
      {"keybind_rstick_left", "Left"},
      {"keybind_rstick_right", "Right"},
      {"keybind_rstick_press", ""},
      {"keybind_a", "Space"},
      {"keybind_b", "K"},
      {"keybind_x", "J"},
      {"keybind_y", "L"},
      {"keybind_right_trigger", "Shift"},
      {"keybind_left_trigger", "Control"},
      {"keybind_left_shoulder", "Q"},
      {"keybind_right_shoulder", "E"},
      {"keybind_start", "Return"},
      {"keybind_back", "Escape,Backspace"},
      {"keybind_dpad_up", "1"},
      {"keybind_dpad_down", "2"},
      {"keybind_dpad_left", "3"},
      {"keybind_dpad_right", "4"},
  };
  int changed = 0;
  for (const auto& [name, value] : kLayout) {
    if (rex::cvar::GetFlagSource(name) != rex::cvar::Source::kDefault) continue;
    if (rex::cvar::SetFlagByName(name, value)) ++changed;
  }
  REXLOG_INFO("Keyboard layout (WASD) applied to {} input settings", changed);
}

}  // namespace fifa08::keyboard

#endif
