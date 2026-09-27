FROM r-base:4.4.1@sha256:e7032f2f6fd273ee944a717b436bc66d1a89b1b90a9bbcaafcf1318d68a7d8b2

# fs (a testthat dependency) links against libuv; without it the build fails.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libuv1-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# testthat 3.3.2 and its dependencies from a DATED Posit Package Manager CRAN
# snapshot: rebuilding this image next year installs the same versions, not
# whatever CRAN holds that day. Built from source (r-base carries the
# toolchain). The version is asserted so a snapshot change cannot slip past.
ARG CRAN_SNAPSHOT=https://packagemanager.posit.co/cran/2026-09-01
RUN Rscript -e "options(repos = c(CRAN = '${CRAN_SNAPSHOT}'), Ncpus = 4L); \
      install.packages('testthat', lib = .Library); \
      stopifnot(as.character(packageVersion('testthat')) == '3.3.2')" \
    && rm -rf /tmp/Rtmp* /tmp/downloaded_packages
COPY run-tests /opt/factory/run-tests
RUN chmod 0555 /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-test-r" \
      org.opencontainers.image.description="Offline testthat runner for R runtime QC"
