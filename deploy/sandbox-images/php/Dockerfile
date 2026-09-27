FROM php:8.3-cli@sha256:ea7f9ff498ef56523495d718934df94fec07e96b59c6ad9dd895e7be8b0afcd1

# PHPUnit 11.5.39 as a self-contained phar (PHPUnit 11 supports PHP 8.2+).
ADD --checksum=sha256:63601d96eca81db5ab675657f4a0b4056ff7b4acfe0d5767a1d74f50b626456d \
    https://phar.phpunit.de/phpunit-11.5.39.phar \
    /opt/factory/phpunit.phar
COPY run-tests /opt/factory/run-tests
RUN chmod 0444 /opt/factory/phpunit.phar && chmod 0555 /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-test-php" \
      org.opencontainers.image.description="Offline PHPUnit 11 runner for runtime QC"
