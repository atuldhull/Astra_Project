# PX4 SITL (SIH: PX4's built-in headless simulator, no Gazebo), pinned, with the ASTRA
# simulator-only GPS patch (src/modules/simulation/sensor_gps_sim). Flight stack untouched.
# Build:  docker build -t astra/px4-sitl:v1.17.0 sim/px4
FROM ubuntu:22.04
ARG PX4_TAG=v1.17.0
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates sudo lsb-release tzdata python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch ${PX4_TAG} --recurse-submodules --shallow-submodules \
        https://github.com/PX4/PX4-Autopilot.git px4
WORKDIR /src/px4
RUN bash Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools && rm -rf /var/lib/apt/lists/*
COPY astra-px4-gps.patch /src/astra-px4-gps.patch
RUN git apply --check /src/astra-px4-gps.patch && git apply /src/astra-px4-gps.patch
RUN make px4_sitl_default && git rev-parse HEAD > /src/PX4_COMMIT
# bc: rcS scales link-loss timeouts by PX4_SIM_SPEED_FACTOR with it (missing => failsafes unscaled)
RUN apt-get update && apt-get install -y --no-install-recommends bc && rm -rf /var/lib/apt/lists/*
WORKDIR /src/px4/build/px4_sitl_default/rootfs
# SIH quadrotor airframe. MAVLink GCS link on UDP 18570 (set MAV_0_BROADCAST=1 so Docker port
# forwarding can reach it). Launched from rootfs via a shell so PX4 links etc/ into the working dir.
ENV PX4_SYS_AUTOSTART=10040 PX4_SIM_MODEL=sihsim_quadx HEADLESS=1
ENTRYPOINT ["bash", "-c", "cd /src/px4/build/px4_sitl_default/rootfs && exec ../bin/px4 -d ../etc"]
