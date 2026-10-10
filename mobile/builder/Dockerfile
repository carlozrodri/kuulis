# APK builder that runs on our own server (Coolify app kuulis-builder-qa) instead of the EAS Build queue.
# Coolify rebuilds this image when mobile/ changes on the `qa` branch; on start the container compiles the
# app with `eas build --local` (same credentials and EAS env vars as the cloud build) and uploads the APK to
# S3 under builds/<env>/. See docs/deployment.md ("Compilador de APK").
# Build context: mobile/ (Coolify base directory /mobile, Dockerfile /builder/Dockerfile).
FROM node:22-bookworm

ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_NDK_VERSION=27.1.12297006 \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    CI=1 \
    EXPO_NO_TELEMETRY=1 \
    EAS_NO_VCS=1 \
    EAS_SKIP_AUTO_FINGERPRINT=1 \
    GRADLE_USER_HOME=/cache/gradle \
    npm_config_cache=/cache/npm
ENV ANDROID_NDK_HOME=$ANDROID_HOME/ndk/$ANDROID_NDK_VERSION \
    PATH=$PATH:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jdk-headless unzip python3-boto3 \
 && rm -rf /var/lib/apt/lists/*

# Android SDK: the versions React Native 0.86 / Expo SDK 57 compile with (node_modules/react-native/gradle/libs.versions.toml).
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
 && curl -fsSL -o /tmp/tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
 && unzip -q /tmp/tools.zip -d /tmp/tools && mv /tmp/tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
 && rm -rf /tmp/tools /tmp/tools.zip \
 && yes | sdkmanager --licenses > /dev/null \
 && sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0" "ndk;$ANDROID_NDK_VERSION" "cmake;3.22.1" > /dev/null

RUN npm install -g eas-cli@latest

WORKDIR /src
COPY . .
RUN rm -rf node_modules android ios && chmod +x builder/build.sh

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/ || exit 1
CMD ["/src/builder/build.sh"]
