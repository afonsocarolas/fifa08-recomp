#pragma once

// On-screen gamepad for touch screens (Android build).
//
// A virtual SDL gamepad ("Touch Controls") is fed from finger events, so the
// SDK's SDL input driver sees an ordinary Xbox-style controller. An ImGui
// overlay draws the controls on top of the game. Layout (landscape):
//   left half:  floating left stick (appears where the thumb lands)
//   right side: A / B / X / Y diamond, RB + RT above it
//   left top:   LB + LT
//   top center: Back + Start
// Disable with --touch_controls=false.

#ifndef __ANDROID__
namespace rex::ui {
class ImGuiDrawer;
}
namespace fifa08::touch {
inline void Start(rex::ui::ImGuiDrawer*) {}
}  // namespace fifa08::touch
#else

#include <algorithm>
#include <atomic>
#include <cmath>
#include <mutex>
#include <unordered_map>

#include <SDL3/SDL.h>
#include <imgui.h>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/ui/imgui_dialog.h>
#include <rex/ui/imgui_drawer.h>

REXCVAR_DEFINE_BOOL(touch_controls, true, "Input", "Show the on-screen gamepad on touch screens");

namespace fifa08::touch {

struct Button {
  const char* label;
  SDL_GamepadButton button;  // SDL_GAMEPAD_BUTTON_INVALID for triggers
  SDL_GamepadAxis trigger;   // SDL_GAMEPAD_AXIS_INVALID for buttons
  float x, y;                // centre: x in screen widths, y in screen heights
  float r;                   // radius in screen heights
  ImU32 color;
};

// Xbox colours for the face buttons.
inline const Button kButtons[] = {
    {"A", SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_AXIS_INVALID, 0.865f, 0.80f, 0.075f, IM_COL32(96, 185, 72, 255)},
    {"B", SDL_GAMEPAD_BUTTON_EAST, SDL_GAMEPAD_AXIS_INVALID, 0.935f, 0.65f, 0.075f, IM_COL32(220, 60, 50, 255)},
    {"X", SDL_GAMEPAD_BUTTON_WEST, SDL_GAMEPAD_AXIS_INVALID, 0.795f, 0.65f, 0.075f, IM_COL32(50, 120, 220, 255)},
    {"Y", SDL_GAMEPAD_BUTTON_NORTH, SDL_GAMEPAD_AXIS_INVALID, 0.865f, 0.50f, 0.075f, IM_COL32(240, 190, 40, 255)},
    {"RB", SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, SDL_GAMEPAD_AXIS_INVALID, 0.80f, 0.22f, 0.065f, IM_COL32(200, 200, 200, 255)},
    {"RT", SDL_GAMEPAD_BUTTON_INVALID, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, 0.93f, 0.30f, 0.075f, IM_COL32(200, 200, 200, 255)},
    {"LB", SDL_GAMEPAD_BUTTON_LEFT_SHOULDER, SDL_GAMEPAD_AXIS_INVALID, 0.20f, 0.22f, 0.065f, IM_COL32(200, 200, 200, 255)},
    {"LT", SDL_GAMEPAD_BUTTON_INVALID, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, 0.07f, 0.30f, 0.075f, IM_COL32(200, 200, 200, 255)},
    {"BACK", SDL_GAMEPAD_BUTTON_BACK, SDL_GAMEPAD_AXIS_INVALID, 0.42f, 0.08f, 0.05f, IM_COL32(200, 200, 200, 255)},
    {"START", SDL_GAMEPAD_BUTTON_START, SDL_GAMEPAD_AXIS_INVALID, 0.58f, 0.08f, 0.05f, IM_COL32(200, 200, 200, 255)},
};
constexpr int kNumButtons = int(sizeof(kButtons) / sizeof(kButtons[0]));
constexpr float kStickRadius = 0.13f;  // screen heights
constexpr int kStick = -1;              // finger owner id for the stick
constexpr Uint64 kMinPressMs = 150;
// The SDK's SDL input driver only learns about gamepads from "gamepad added"
// events, which it starts watching a moment after the dialogs are created, so
// the virtual gamepad is attached this long after Start().
constexpr Uint64 kAttachDelayMs = 1500;

struct State {
  std::mutex mutex;
  SDL_Joystick* joystick = nullptr;
  float aspect = 16.0f / 9.0f;  // width / height, updated from the overlay
  std::unordered_map<SDL_FingerID, int> fingers;  // finger -> button index or kStick
  bool pressed[kNumButtons] = {};
  // A quick tap can start and end between two game polls (the game polls once
  // per frame, slowly on phones), so every press is held for a minimum time.
  Uint64 hold_until[kNumButtons] = {};
  bool stick_active = false;
  float stick_cx = 0, stick_cy = 0;  // stick centre (normalized window coords)
  float stick_dx = 0, stick_dy = 0;  // knob offset, -1..1 of the radius
};

inline State& S() {
  static State s;
  return s;
}

inline Sint16 AxisValue(float v) { return Sint16(std::clamp(v, -1.0f, 1.0f) * 32767.0f); }

inline void ApplyLocked(State& s) {
  if (!s.joystick) return;
  SDL_SetJoystickVirtualAxis(s.joystick, SDL_GAMEPAD_AXIS_LEFTX, AxisValue(s.stick_dx));
  SDL_SetJoystickVirtualAxis(s.joystick, SDL_GAMEPAD_AXIS_LEFTY, AxisValue(s.stick_dy));
  for (int i = 0; i < kNumButtons; ++i) {
    const Button& b = kButtons[i];
    const bool down = s.pressed[i] || SDL_GetTicks() < s.hold_until[i];
    if (b.button != SDL_GAMEPAD_BUTTON_INVALID) {
      SDL_SetJoystickVirtualButton(s.joystick, b.button, down);
    } else {
      // Rest at the bottom of the axis: with a full-range trigger mapping, 0
      // would read as half pressed.
      SDL_SetJoystickVirtualAxis(s.joystick, b.trigger, down ? SDL_JOYSTICK_AXIS_MAX : SDL_JOYSTICK_AXIS_MIN);
    }
  }
}

// Which button (index) is under normalized point (x, y), or -1.
inline int HitButton(const State& s, float x, float y) {
  int best = -1;
  float best_d = 1e9f;
  for (int i = 0; i < kNumButtons; ++i) {
    const Button& b = kButtons[i];
    float dx = (x - b.x) * s.aspect, dy = y - b.y;  // in screen heights
    float d = std::sqrt(dx * dx + dy * dy);
    if (d < b.r * 1.35f && d < best_d) {
      best = i;
      best_d = d;
    }
  }
  return best;
}

inline void UpdateStick(State& s, float x, float y) {
  float dx = (x - s.stick_cx) * s.aspect / kStickRadius;
  float dy = (y - s.stick_cy) / kStickRadius;
  float len = std::sqrt(dx * dx + dy * dy);
  if (len > 1.0f) {
    dx /= len;
    dy /= len;
  }
  s.stick_dx = dx;
  s.stick_dy = dy;
}

inline bool SDLCALL OnEvent(void*, SDL_Event* e) {
  if (e->type != SDL_EVENT_FINGER_DOWN && e->type != SDL_EVENT_FINGER_MOTION &&
      e->type != SDL_EVENT_FINGER_UP && e->type != SDL_EVENT_FINGER_CANCELED) {
    return true;
  }
  State& s = S();
  std::lock_guard lock(s.mutex);
  const SDL_FingerID id = e->tfinger.fingerID;
  const float x = e->tfinger.x, y = e->tfinger.y;
  switch (e->type) {
    case SDL_EVENT_FINGER_DOWN: {
      int hit = HitButton(s, x, y);
      if (hit >= 0) {
        s.fingers[id] = hit;
        s.pressed[hit] = true;
        s.hold_until[hit] = SDL_GetTicks() + kMinPressMs;
      } else if (x < 0.5f && y > 0.35f && !s.stick_active) {
        s.fingers[id] = kStick;
        s.stick_active = true;
        s.stick_cx = x;
        s.stick_cy = y;
        s.stick_dx = s.stick_dy = 0;
      }
      break;
    }
    case SDL_EVENT_FINGER_MOTION: {
      auto it = s.fingers.find(id);
      if (it == s.fingers.end()) break;
      if (it->second == kStick) {
        UpdateStick(s, x, y);
      } else {
        // Let a thumb slide from one face button to another.
        int hit = HitButton(s, x, y);
        if (hit >= 0 && hit != it->second) {
          s.pressed[it->second] = false;
          it->second = hit;
          s.pressed[hit] = true;
          s.hold_until[hit] = SDL_GetTicks() + kMinPressMs;
        }
      }
      break;
    }
    default: {  // up / canceled
      auto it = s.fingers.find(id);
      if (it == s.fingers.end()) break;
      if (it->second == kStick) {
        s.stick_active = false;
        s.stick_dx = s.stick_dy = 0;
      } else {
        s.pressed[it->second] = false;
      }
      s.fingers.erase(it);
      break;
    }
  }
  // No SDL joystick calls here: event watchers run under SDL's event lock,
  // while SDL_UpdateJoysticks (joystick lock held) can push events, so
  // calling SDL_SetJoystickVirtual* from here deadlocks. OnUpdate applies it.
  return true;
}

// Virtual joystick Update callback: runs inside SDL_UpdateJoysticks with the
// joystick lock held, the one place where setting the virtual state is safe.
inline void SDLCALL OnUpdate(void*) {
  State& s = S();
  std::lock_guard lock(s.mutex);
  ApplyLocked(s);
}

// Creates and opens the virtual gamepad. Called without our mutex held: OnUpdate
// takes it while SDL holds the joystick lock, so the lock order must always be
// joystick lock -> our mutex.
inline void AttachGamepad() {
  SDL_VirtualJoystickDesc desc;
  SDL_INIT_INTERFACE(&desc);
  desc.type = SDL_JOYSTICK_TYPE_GAMEPAD;
  desc.naxes = SDL_GAMEPAD_AXIS_COUNT;
  desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
  desc.name = "Touch Controls";
  desc.Update = OnUpdate;
  SDL_JoystickID id = SDL_AttachVirtualJoystick(&desc);
  if (!id) {
    REXLOG_ERROR("Touch controls: could not create the virtual gamepad: {}", SDL_GetError());
    return;
  }
  SDL_Joystick* joystick = SDL_OpenJoystick(id);
  {
    std::lock_guard lock(S().mutex);
    S().joystick = joystick;
  }
  REXLOG_INFO("Touch controls: virtual gamepad {} attached", id);
}

class Overlay final : public rex::ui::ImGuiDialog {
 public:
  explicit Overlay(rex::ui::ImGuiDrawer* drawer)
      : ImGuiDialog(drawer), attach_at_(SDL_GetTicks() + kAttachDelayMs) {}

 protected:
  void OnDraw(ImGuiIO& io) override {
    if (!attached_ && SDL_GetTicks() >= attach_at_) {
      attached_ = true;
      AttachGamepad();
    }
    const float w = io.DisplaySize.x, h = io.DisplaySize.y;
    if (w <= 0 || h <= 0) return;
    State& s = S();
    std::lock_guard lock(s.mutex);
    s.aspect = w / h;
    ImDrawList* dl = ImGui::GetForegroundDrawList();
    const float font = h * 0.035f;

    for (int i = 0; i < kNumButtons; ++i) {
      const Button& b = kButtons[i];
      ImVec2 c(b.x * w, b.y * h);
      float r = b.r * h;
      const bool down = s.pressed[i] || SDL_GetTicks() < s.hold_until[i];
      ImU32 fill = down ? (b.color & 0x00FFFFFF) | 0xC0000000 : IM_COL32(0, 0, 0, 70);
      dl->AddCircleFilled(c, r, fill, 48);
      dl->AddCircle(c, r, (b.color & 0x00FFFFFF) | 0xB0000000, 48, h * 0.005f);
      ImVec2 ts = ImGui::CalcTextSize(b.label);
      float scale = font / ImGui::GetFontSize();
      ImVec2 pos(c.x - ts.x * scale * 0.5f, c.y - ts.y * scale * 0.5f);
      dl->AddText(nullptr, font, pos, IM_COL32(255, 255, 255, 220), b.label);
    }

    // Stick: drawn where it is held, or a faint hint where it usually sits.
    ImVec2 base = s.stick_active ? ImVec2(s.stick_cx * w, s.stick_cy * h) : ImVec2(0.17f * w, 0.72f * h);
    float r = kStickRadius * h;
    dl->AddCircleFilled(base, r, IM_COL32(0, 0, 0, s.stick_active ? 90 : 45), 64);
    dl->AddCircle(base, r, IM_COL32(255, 255, 255, s.stick_active ? 160 : 80), 64, h * 0.005f);
    ImVec2 knob(base.x + s.stick_dx * r, base.y + s.stick_dy * r);
    dl->AddCircleFilled(knob, r * 0.45f, IM_COL32(255, 255, 255, s.stick_active ? 170 : 70), 48);
  }

 private:
  Uint64 attach_at_;
  bool attached_ = false;
};

// Shows the overlay and starts listening for fingers; the virtual gamepad
// itself is attached by the overlay after kAttachDelayMs. Call once, after SDL
// is up.
inline void Start(rex::ui::ImGuiDrawer* drawer) {
  if (!REXCVAR_GET(touch_controls) || !drawer) return;
  // Joystick only: initializing the gamepad subsystem here, before the SDK's
  // input driver does, would also swallow the "gamepad added" events it relies on.
  SDL_InitSubSystem(SDL_INIT_JOYSTICK);
  // Fingers drive the pad; don't also turn them into mouse clicks.
  SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
  SDL_AddEventWatch(OnEvent, nullptr);
  new Overlay(drawer);  // owned by the drawer
  REXLOG_INFO("Touch controls enabled");
}

}  // namespace fifa08::touch

#endif  // __ANDROID__
