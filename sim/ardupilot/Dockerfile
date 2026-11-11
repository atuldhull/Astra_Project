# ArduPilot SITL, pinned, headless. Copter (default) or Plane.
# Build:  docker build -t astra/ardupilot-sitl:copter-4.7.2 sim/ardupilot
#         docker build -t astra/ardupilot-sitl:plane-4.7.2 --build-arg AP_TAG=Plane-4.7.2 --build-arg AP_VEHICLE=plane sim/ardupilot
# The binary is run directly (no sim_vehicle.py / MAVProxy): MAVProxy's GCS
# failsafes misbehave above ~10x speed-up, and we want zero hidden processes.

ARG UBUNTU=22.04
FROM ubuntu:${UBUNTU} AS build
ARG AP_TAG=Copter-4.7.2
ARG AP_VEHICLE=copter
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates python3 python3-pip python3-dev g++ make pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir empy==3.3.4 pexpect future
WORKDIR /src
RUN git clone --depth 1 --branch ${AP_TAG} --recurse-submodules --shallow-submodules \
        https://github.com/ArduPilot/ardupilot.git ardupilot
WORKDIR /src/ardupilot
# Simulator-only patch (libraries/SITL): adds SIM_GPS*_SPFV velocity bias. The
# vehicle code under test (AP_GPS, EKF, flight modes) is untouched.
COPY astra-sitl-gps.patch /src/astra-sitl-gps.patch
RUN git apply --check /src/astra-sitl-gps.patch && git apply /src/astra-sitl-gps.patch
RUN ./waf configure --board sitl && ./waf ${AP_VEHICLE}
RUN git rev-parse HEAD > /src/AP_COMMIT

FROM ubuntu:${UBUNTU}
ARG AP_TAG=Copter-4.7.2
ARG AP_VEHICLE=copter
LABEL org.opencontainers.image.title="astra-ardupilot-sitl" \
      org.opencontainers.image.version="${AP_TAG}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/ardupilot/build/sitl/bin/ /opt/ardupilot/bin/
COPY --from=build /src/ardupilot/Tools/autotest/default_params/ /opt/ardupilot/params/
COPY --from=build /src/ardupilot/Tools/autotest/models/ /opt/ardupilot/models/
# Stable names regardless of vehicle; "arducopter"/"copter.parm" kept as aliases for older runner code.
# Copter defaults live in default_params/copter.parm, Plane's in models/plane.parm (as sim_vehicle uses).
RUN P=/opt/ardupilot/params/${AP_VEHICLE}.parm; [ -f "$P" ] || P=/opt/ardupilot/models/${AP_VEHICLE}.parm; \
    test -f "$P" \
 && ln -s /opt/ardupilot/bin/ardu${AP_VEHICLE} /opt/ardupilot/vehicle \
 && ln -s "$P" /opt/ardupilot/vehicle.parm \
 && ln -s /opt/ardupilot/bin/ardu${AP_VEHICLE} /opt/ardupilot/arducopter \
 && ln -s "$P" /opt/ardupilot/copter.parm
COPY --from=build /src/ardupilot/Tools/autotest/locations.txt /opt/ardupilot/locations.txt
COPY --from=build /src/AP_COMMIT /opt/ardupilot/AP_COMMIT
WORKDIR /work
# Unmodified upstream binary. ASTRA talks to it over MAVLink TCP (5760 + 10*instance).
ENTRYPOINT ["/opt/ardupilot/vehicle"]
