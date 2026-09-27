FROM sbtscala/scala-sbt:eclipse-temurin-jammy-21.0.2_13_1.9.9_3.4.0@sha256:6a1a1c8f9881cf4d2b9963cb9945e6209087538e79d9237072c6ef09ca4c3ef6

# ScalaTest 3.2.19 for Scala 3 as an explicit bill of materials: the complete
# compile/runtime closure resolved from Maven Central POMs on 2026-09-27, every
# jar's SHA-1 checked against Central and its SHA-256 enforced below. The Scala
# standard library is deliberately excluded -- the image's scalac 3.4.0 supplies
# it, and two copies on one classpath is how version skew hides.
#
#   org.scala-lang.modules:scala-xml_3:2.1.0
#   org.scalactic:scalactic_3:3.2.19
#   org.scalatest:scalatest-compatible:3.2.19
#   org.scalatest:scalatest-core_3:3.2.19
#   org.scalatest:scalatest-diagrams_3:3.2.19
#   org.scalatest:scalatest-featurespec_3:3.2.19
#   org.scalatest:scalatest-flatspec_3:3.2.19
#   org.scalatest:scalatest-freespec_3:3.2.19
#   org.scalatest:scalatest-funspec_3:3.2.19
#   org.scalatest:scalatest-funsuite_3:3.2.19
#   org.scalatest:scalatest-matchers-core_3:3.2.19
#   org.scalatest:scalatest-mustmatchers_3:3.2.19
#   org.scalatest:scalatest-propspec_3:3.2.19
#   org.scalatest:scalatest-refspec_3:3.2.19
#   org.scalatest:scalatest-shouldmatchers_3:3.2.19
#   org.scalatest:scalatest-wordspec_3:3.2.19
#   org.scalatest:scalatest_3:3.2.19
ADD --checksum=sha256:48f22343575f4b1d6550eecc42d4b7f0a0d30223c72f015d8d893feab4cbeecd https://repo1.maven.org/maven2/org/scala-lang/modules/scala-xml_3/2.1.0/scala-xml_3-2.1.0.jar /opt/factory/scalatest/scala-xml_3-2.1.0.jar
ADD --checksum=sha256:26ef71a6d0993301d28d9693bada18ff81b373336b70368fcff01ed4eb4b958e https://repo1.maven.org/maven2/org/scalactic/scalactic_3/3.2.19/scalactic_3-3.2.19.jar /opt/factory/scalatest/scalactic_3-3.2.19.jar
ADD --checksum=sha256:5dc6b8fa5396fe9e1a7c2b72df174a8eb3e92770cdc3e70636d3eba673cd0da3 https://repo1.maven.org/maven2/org/scalatest/scalatest-compatible/3.2.19/scalatest-compatible-3.2.19.jar /opt/factory/scalatest/scalatest-compatible-3.2.19.jar
ADD --checksum=sha256:f6e3d38c2034a9cab7313f644d8a933bf1b5241ff35002cc76916a427a826223 https://repo1.maven.org/maven2/org/scalatest/scalatest-core_3/3.2.19/scalatest-core_3-3.2.19.jar /opt/factory/scalatest/scalatest-core_3-3.2.19.jar
ADD --checksum=sha256:835acf8ec2cb0d39beb1052ee2139029fdac28d172fc867db89ff49d640b255e https://repo1.maven.org/maven2/org/scalatest/scalatest-diagrams_3/3.2.19/scalatest-diagrams_3-3.2.19.jar /opt/factory/scalatest/scalatest-diagrams_3-3.2.19.jar
ADD --checksum=sha256:3d49deeede2cd01578e037065862d7734afd3a6330c35dc3c4906f53f57302db https://repo1.maven.org/maven2/org/scalatest/scalatest-featurespec_3/3.2.19/scalatest-featurespec_3-3.2.19.jar /opt/factory/scalatest/scalatest-featurespec_3-3.2.19.jar
ADD --checksum=sha256:85a6fb2285f20445615c6780a498c3bca99e4c2aad32fab6f74202bdc61e56a9 https://repo1.maven.org/maven2/org/scalatest/scalatest-flatspec_3/3.2.19/scalatest-flatspec_3-3.2.19.jar /opt/factory/scalatest/scalatest-flatspec_3-3.2.19.jar
ADD --checksum=sha256:ebc8573874766368316366495dcdfe0cca6d8082dc9cc08b5a2fd0834cdaecc0 https://repo1.maven.org/maven2/org/scalatest/scalatest-freespec_3/3.2.19/scalatest-freespec_3-3.2.19.jar /opt/factory/scalatest/scalatest-freespec_3-3.2.19.jar
ADD --checksum=sha256:872b6889fac777aa813d21fb5f1e89710407785a61eb18a570142b6be10389a7 https://repo1.maven.org/maven2/org/scalatest/scalatest-funspec_3/3.2.19/scalatest-funspec_3-3.2.19.jar /opt/factory/scalatest/scalatest-funspec_3-3.2.19.jar
ADD --checksum=sha256:42129cc156bd8978d9a438abd57001fc42ababf18f6178cbee91d0a9489334e0 https://repo1.maven.org/maven2/org/scalatest/scalatest-funsuite_3/3.2.19/scalatest-funsuite_3-3.2.19.jar /opt/factory/scalatest/scalatest-funsuite_3-3.2.19.jar
ADD --checksum=sha256:723fecdf0ea4542947ef5174068c4e05cd2145a3dcb6ffc797079368c94a187e https://repo1.maven.org/maven2/org/scalatest/scalatest-matchers-core_3/3.2.19/scalatest-matchers-core_3-3.2.19.jar /opt/factory/scalatest/scalatest-matchers-core_3-3.2.19.jar
ADD --checksum=sha256:837f76b73ff299fb6748ba0aff4eb7c9d9c00252741ad2bc15af3998d2e0558c https://repo1.maven.org/maven2/org/scalatest/scalatest-mustmatchers_3/3.2.19/scalatest-mustmatchers_3-3.2.19.jar /opt/factory/scalatest/scalatest-mustmatchers_3-3.2.19.jar
ADD --checksum=sha256:6b033e73f3a53717a32a0d4d35ae2021a0afe8a028c42da62fb937932934bce3 https://repo1.maven.org/maven2/org/scalatest/scalatest-propspec_3/3.2.19/scalatest-propspec_3-3.2.19.jar /opt/factory/scalatest/scalatest-propspec_3-3.2.19.jar
ADD --checksum=sha256:827b78a65c25a1dc4af747a7711e24c785fae92c39600fd357a7d486fcce2e7a https://repo1.maven.org/maven2/org/scalatest/scalatest-refspec_3/3.2.19/scalatest-refspec_3-3.2.19.jar /opt/factory/scalatest/scalatest-refspec_3-3.2.19.jar
ADD --checksum=sha256:76ddce37f710ea96bdb3eebcb4bb0a0125fc70fb2ebaa7cc74c9bd28284b6a23 https://repo1.maven.org/maven2/org/scalatest/scalatest-shouldmatchers_3/3.2.19/scalatest-shouldmatchers_3-3.2.19.jar /opt/factory/scalatest/scalatest-shouldmatchers_3-3.2.19.jar
ADD --checksum=sha256:c6acce0958b086cb857c4da6107f903b6166a46dfa251f54d3a0869212e229c7 https://repo1.maven.org/maven2/org/scalatest/scalatest-wordspec_3/3.2.19/scalatest-wordspec_3-3.2.19.jar /opt/factory/scalatest/scalatest-wordspec_3-3.2.19.jar
ADD --checksum=sha256:cd886ba42615fe0d730dd57197e6ee53eeb062cfd0b4d8c5d9757c977c0fdcf8 https://repo1.maven.org/maven2/org/scalatest/scalatest_3/3.2.19/scalatest_3-3.2.19.jar /opt/factory/scalatest/scalatest_3-3.2.19.jar
COPY run-tests /opt/factory/run-tests
RUN chmod 0444 /opt/factory/scalatest/*.jar && chmod 0555 /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-test-scala" \
      org.opencontainers.image.description="Offline ScalaTest runner for Scala runtime QC"
