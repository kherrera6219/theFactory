FROM eclipse-temurin:21-jdk@sha256:efd34b940f2d5a621605c8531c2afb7759c936b6c2ef637a69aa3bf3e1e789d1

# JUnit 5 via the Platform Console Standalone launcher: one self-contained jar
# with the Jupiter API, engine and launcher. Checksum verified at build time.
ADD --checksum=sha256:b016ef6b1c3454d6d7c2c88ce081dabf289699686af6622d6e4e2e1b54b4a2fc \
    https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.11.4/junit-platform-console-standalone-1.11.4.jar \
    /opt/factory/junit-console.jar
COPY run-tests /opt/factory/run-tests
RUN chmod 0444 /opt/factory/junit-console.jar && chmod 0555 /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-test-java" \
      org.opencontainers.image.description="Offline JUnit 5 runner for runtime QC"
