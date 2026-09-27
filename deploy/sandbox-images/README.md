# Vendored test-runner sandbox images

Runtime QC executes generated tests with `--network=none`, so a test framework
must already be inside the image. The official language images carry only the
toolchain; these images add the one framework the Tester agent writes tests for,
at a pinned version, verified by checksum at build time.

| Image | Base (pinned by digest) | Adds |
|---|---|---|
| `thefactory/sandbox-test-java:1` | `eclipse-temurin:21-jdk` | JUnit Platform Console Standalone 1.11.4 (JUnit 5) |
| `thefactory/sandbox-test-kotlin:1` | `zenika/kotlin` (kotlinc 1.4.10) | JUnit console 1.11.4, kotlin-test + kotlin-test-junit5 1.4.10 |
| `thefactory/sandbox-test-scala:1` | `sbtscala/scala-sbt` (Scala 3.4.0) | ScalaTest 3.2.19, resolved by coursier 2.1.25 at build time |
| `thefactory/sandbox-test-php:1` | `php:8.3-cli` | PHPUnit 11.5.39 phar |
| `thefactory/sandbox-test-r:1` | `r-base:4.4.1` | testthat, from a dated Posit Package Manager CRAN snapshot |
| `thefactory/sandbox-test-node:1` | `node:20-slim` | vitest 4.1.11 + typescript 5.9.3, from a committed lockfile |

Each image carries `/opt/factory/run-tests <artifact> <test-file>`, which copies
the read-only `/workspace` into the container's tmpfs, applies the language's
file-naming rule (a public JUnit/PHPUnit class must live in a file of the same
name, while the factory writes `test_<artifact>`), compiles, and runs. Its exit
code is the verdict.

Build them with `make sandbox-images` (also run by `make up`). The images build
from locally cached bases, so a Docker Hub rate limit does not block them once
the bases are present. Bump the tag when a Dockerfile changes: the runtime-QC
table (`rqca_agent._VENDORED_TEST_RUNTIMES`) names the tag it was verified with.

If an image is missing, runtime QC reports `DRY_RUN` with
`sandbox infrastructure error: ... unavailable` — never a FAIL of the artifact.
