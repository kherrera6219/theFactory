FROM eclipse-temurin:21-jdk@sha256:efd34b940f2d5a621605c8531c2afb7759c936b6c2ef637a69aa3bf3e1e789d1

# Replaces zenika/kotlin (Oracle Linux 7.6, JRE 12, kotlinc 1.4.10 -- all
# end-of-life) as the Kotlin sandbox for BOTH running the artifact and running
# its tests, so the two compile with the same compiler.
#
# Kotlin 2.4.20 compiler; the zip's published SHA-256 was checked against the
# download on 2026-09-27 and is enforced here. It ships kotlin-test and
# kotlin-test-junit5 in lib/. The JDK's own `jar` tool unpacks it, so no extra
# package is installed into the image.
ADD --checksum=sha256:59e9ca74c7904ef2c122b12114937673ccce68de820a663f0ed66ccf8799e0b7 \
    https://github.com/JetBrains/kotlin/releases/download/v2.4.20/kotlin-compiler-2.4.20.zip \
    /tmp/kotlin-compiler.zip
ADD --checksum=sha256:b016ef6b1c3454d6d7c2c88ce081dabf289699686af6622d6e4e2e1b54b4a2fc \
    https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.11.4/junit-platform-console-standalone-1.11.4.jar \
    /opt/factory/junit-console.jar
RUN cd /opt && jar xf /tmp/kotlin-compiler.zip && rm /tmp/kotlin-compiler.zip \
    && chmod 0555 /opt/kotlinc/bin/* && chmod 0444 /opt/factory/junit-console.jar
COPY run-tests /opt/factory/run-tests
RUN chmod 0555 /opt/factory/run-tests

ENV PATH="/opt/kotlinc/bin:${PATH}"

LABEL org.opencontainers.image.title="thefactory sandbox-kotlin" \
      org.opencontainers.image.description="Kotlin 2.4.20 runtime and offline kotlin-test/JUnit 5 runner for runtime QC"
