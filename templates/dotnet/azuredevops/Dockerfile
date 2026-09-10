FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["src/${{ values.repoName }}.csproj", "src/"]
RUN dotnet restore "src/${{ values.repoName }}.csproj"
COPY src/ ./src/
RUN dotnet publish "src/${{ values.repoName }}.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
ENTRYPOINT ["dotnet", "${{ values.repoName }}.dll"]
