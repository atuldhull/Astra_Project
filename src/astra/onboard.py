"""ASTRA Shield: onboard GNSS-consistency monitor (channel C3) as an ArduPilot Lua script.

Runs on the vehicle, using only the scripting API available in ArduPilot 4.7.2 (gps:location,
gps:velocity, gps:last_fix_time_ms). Per GNSS fix it computes

    r = (p(t) − p(t−2 s)) / Δt  −  v_reported(t − 1 s)        (position-rate vs reported velocity)

takes 4-second block medians, normalises with a 2×2 inverse covariance, and runs a CUSUM. On alarm it
sends a GCS warning (and logs it). It doesn't change flight behaviour unless ASTRA_ACTION ≥ 1.

Two modes:
  * log-only (calibration=None): logs block residuals (ASTM: rN, rE) for calibration.
  * armed (calibration given): also runs the CUSUM with baked constants and alarms.

Optical-flow rates aren't exposed to Lua in 4.7.2, so channel C2 can't run onboard yet
(it needs an upstream binding for AP_OpticalFlow::flowRate()/bodyRate()).
"""

from __future__ import annotations

import numpy as np

BLOCK_S = 4.0
SPAN_S = 2.0


def lua_monitor(cal: dict | None = None, action: int = 0) -> str:
    if cal is None:
        s00 = s01 = s11 = 0.0
        k = h = 0.0
        armed = "false"
    else:
        S = np.asarray(cal["sigma_inv"])
        s00, s01, s11 = float(S[0, 0]), float(S[0, 1]), float(S[1, 1])
        k, h = float(cal["k"]), float(cal["h"])
        armed = "true"
    return _TEMPLATE.format(s00=repr(s00), s01=repr(s01), s11=repr(s11), k=repr(k), h=repr(h),
                            armed=armed, block_ms=int(BLOCK_S * 1000), span_ms=int(SPAN_S * 1000),
                            action=int(action))


_TEMPLATE = """-- ASTRA Shield: onboard GNSS position/velocity consistency monitor (C3). Generated; do not edit.
-- Detects GNSS spoofing whose reported position drifts away from what the reported velocity implies.
local ARMED = {armed}
local S00, S01, S11 = {s00}, {s01}, {s11}
local K, H = {k}, {h}
local BLOCK_MS, SPAN_MS = {block_ms}, {span_ms}
local ACTION = {action}  -- 0 = alert only, 1 = also switch to LAND on alarm
local M_PER_1E7 = 0.011131949079327357

local hist = {{}}       -- {{t_ms, n, e, vn, ve}}
local lat0, lon0, coslat = nil, nil, 1.0
local last_fix = nil
local blk_n, blk_e = {{}}, {{}}
local blk_start = nil
local cusum = 0.0
local alarmed = false

local function median(t)
  table.sort(t)
  local n = #t
  if n == 0 then return 0 end
  if n % 2 == 1 then return t[(n + 1) // 2] end
  return 0.5 * (t[n // 2] + t[n // 2 + 1])
end

local function airborne()
  if not arming:is_armed() then return false end
  local d = ahrs:get_relative_position_D_home()
  return d ~= nil and -d > 3.0
end

function update()
  if gps:status(0) < 3 then return update, 50 end
  local fix = gps:last_fix_time_ms(0):tofloat()
  if fix == last_fix then return update, 50 end
  last_fix = fix
  local loc = gps:location(0)
  local vel = gps:velocity(0)
  if lat0 == nil then
    lat0, lon0 = loc:lat(), loc:lng()
    coslat = math.cos(math.rad(lat0 * 1e-7))
  end
  local n = (loc:lat() - lat0) * M_PER_1E7
  local e = (loc:lng() - lon0) * M_PER_1E7 * coslat
  hist[#hist + 1] = {{fix, n, e, vel:x(), vel:y()}}
  while #hist > 2 and (fix - hist[1][1]) > SPAN_MS do table.remove(hist, 1) end
  if #hist < 3 or not airborne() then
    blk_n, blk_e, blk_start = {{}}, {{}}, nil
    return update, 50
  end
  local a, b = hist[1], hist[#hist]
  local dt = (b[1] - a[1]) / 1000.0
  if dt < 0.5 * SPAN_MS / 1000.0 then return update, 50 end
  local mid = hist[(#hist + 1) // 2]
  blk_n[#blk_n + 1] = (b[2] - a[2]) / dt - mid[4]
  blk_e[#blk_e + 1] = (b[3] - a[3]) / dt - mid[5]
  if blk_start == nil then blk_start = fix end
  if fix - blk_start >= BLOCK_MS then
    local rn, re = median(blk_n), median(blk_e)
    local q = S00 * rn * rn + 2 * S01 * rn * re + S11 * re * re
    if ARMED then
      cusum = math.max(0.0, cusum + math.min(q, 100.0) - K)
      if cusum > H and not alarmed then
        alarmed = true
        gcs:send_text(2, "ASTRA Shield: GNSS position/velocity inconsistent - possible spoofing")
        if ACTION >= 1 then vehicle:set_mode(9) end
      end
    end
    logger:write("ASTM", "rN,rE,q,S,Al", "ffffB", rn, re, q, cusum, alarmed and 1 or 0)
    blk_n, blk_e, blk_start = {{}}, {{}}, nil
  end
  return update, 50
end

gcs:send_text(6, "ASTRA Shield loaded (" .. (ARMED and "armed" or "log-only") .. ")")
return update, 50
"""
