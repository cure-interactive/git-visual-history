FROM ubuntu:22.04 AS build

RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
    build-essential ca-certificates curl file libboost-filesystem-dev \
    libfreetype6-dev libglew-dev libglm-dev libpcre2-dev libpng-dev \
    libsdl2-dev libsdl2-image-dev pkg-config \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY gource.svg /build/gource.svg
COPY gource.desktop /build/gource.desktop

ARG GOURCE_VERSION=0.56
ARG GOURCE_SHA256=332d89b9a979b17417fbce0edd72b19914f1409fd126a13d11787d0e15dc0d79
ARG LINUXDEPLOY_SHA256=36a2d7e274d12e1050d0e9ecfe11d339ed54720b2bec464c286d53f8b07f5c62

RUN curl --fail --location \
    --output gource.tar.gz \
    "https://github.com/acaudwell/Gource/releases/download/gource-${GOURCE_VERSION}/gource-${GOURCE_VERSION}.tar.gz" \
  && echo "${GOURCE_SHA256}  gource.tar.gz" | sha256sum --check --strict \
  && tar --extract --gzip --file gource.tar.gz \
  && cd "gource-${GOURCE_VERSION}" \
  && ./configure --prefix=/nonexistent/gource-portable \
  && make --jobs="$(nproc)" \
  && cd /build \
  && mkdir -p AppDir/usr/bin/data \
  && cp "gource-${GOURCE_VERSION}/gource" AppDir/usr/bin/gource \
  && cp -a "gource-${GOURCE_VERSION}/data/." AppDir/usr/bin/data/ \
  && mkdir -p AppDir/usr/share/doc/gource \
  && cp "gource-${GOURCE_VERSION}/COPYING" AppDir/usr/share/doc/gource/COPYING \
  && find /usr/share/doc -name copyright -type f -exec cp --parents '{}' AppDir \; \
  && curl --fail --location --output linuxdeploy.AppImage \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage \
  && echo "${LINUXDEPLOY_SHA256}  linuxdeploy.AppImage" | sha256sum --check --strict \
  && chmod +x linuxdeploy.AppImage \
  && LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/pulseaudio:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu \
    ./linuxdeploy.AppImage --appimage-extract-and-run \
    --appdir AppDir \
    --desktop-file gource.desktop \
    --icon-file gource.svg \
  && for library in \
    libGL.so.1 libfreetype.so.6 libOpenGL.so.0 libGLdispatch.so.0 libGLX.so.0 \
    libz.so.1 libasound.so.2 libX11.so.6 libdrm.so.2 libgbm.so.1 \
    libwayland-client.so.0 libxcb.so.1 libexpat.so.1 libX11-xcb.so.1 \
    libgpg-error.so.0; do \
      path=$(find /usr/lib/x86_64-linux-gnu /lib/x86_64-linux-gnu -name "$library" -print -quit); \
      cp -L "$path" "AppDir/usr/lib/$library"; \
    done \
  && LD_LIBRARY_PATH=AppDir/usr/lib:/usr/lib/x86_64-linux-gnu/pulseaudio:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu \
    LDAI_OUTPUT=/build/gource.AppImage \
    ./linuxdeploy.AppImage --appimage-extract-and-run --appdir AppDir --output appimage \
  && chmod +x gource.AppImage \
  && ./gource.AppImage --appimage-extract-and-run -h >/tmp/gource-help.txt \
  && grep -q "Gource v${GOURCE_VERSION}" /tmp/gource-help.txt

FROM scratch AS export
COPY --from=build /build/gource.AppImage /
