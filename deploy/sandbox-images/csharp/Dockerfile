FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:35d40304542c8689331f8cab17c65926cdf48fe711e289321d71924b230a7d29

# C# had no live execution at all (WQ12): the old config called dotnet-script,
# which is not in the SDK image and cannot be installed with --network=none.
#
# Instead, two projects are created and RESTORED here, at build time, while the
# network is available: a console app and an xUnit test project. At run time
# the artifact's sources are dropped into a tmpfs copy of one of them and built
# with --no-restore, so nothing is ever fetched inside the sandbox. NuGet's
# package folder lives under /opt and is read-only at run time.
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_GENERATE_ASPNET_CERTIFICATE=false \
    NUGET_PACKAGES=/opt/factory/nuget

COPY app.csproj /opt/factory/templates/app/app.csproj
COPY tests.csproj /opt/factory/templates/tests/tests.csproj
RUN dotnet restore /opt/factory/templates/app/app.csproj \
    && dotnet restore /opt/factory/templates/tests/tests.csproj \
    && chmod -R a+rX /opt/factory

COPY run-program run-tests /opt/factory/
RUN chmod 0555 /opt/factory/run-program /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-csharp" \
      org.opencontainers.image.description=".NET 10 offline runtime and xUnit runner for C# runtime QC"
